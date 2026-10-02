"""Desired versus last-applied delta for Day 2 SET."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .plan import COMPONENTS, import_blocks, import_nfs, inferred_nfs, site_groups
from .topology import all_services, env, hosts, policy, roots, site_of

# Host prep stays put on a Day 2 run that has no stamp yet. Service files still sync.
UPGRADE_SECTIONS = ("quadlets", "edge", "nfs", "lan_bind", "admin_gui")


def _svc_key(s: dict[str, Any]) -> tuple[str, str]:
    return (s.get("host") or "", s.get("name") or s.get("key") or "")


def service_delta(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, list]:
    want = {_svc_key(s): s for s in all_services(desired)}
    have_list = ((observed.get("site") or {}).get("services") or observed.get("services") or [])
    have = {}
    if isinstance(have_list, list):
        for s in have_list:
            have[_svc_key(s)] = s
    elif isinstance(have_list, dict):
        for host, names in have_list.items():
            for n in names or []:
                have[(host, n)] = {"host": host, "name": n}
    add = [want[k] for k in want if k not in have]
    remove = [have[k] for k in have if k not in want]
    return {"add": add, "remove": remove}


def user_delta(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, list]:
    want = {u.get("name") for u in (site_of(desired).get("users") or []) if u.get("name")}
    obs_users = ((observed.get("site") or {}).get("users") or observed.get("users") or [])
    have = {u.get("name") for u in obs_users if isinstance(u, dict) and u.get("name")}
    return {"add": sorted(want - have), "remove": sorted(have - want)}


def host_names(desired: dict[str, Any]) -> list[str]:
    return [h.get("name") for h in hosts(desired) if h.get("name")]


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    if not path.is_dir():
        h.update(b"missing")
        return h.hexdigest()
    files = [
        p
        for p in path.rglob("*")
        if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts
    ]
    for p in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
        h.update(p.relative_to(path).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _file_hash(path: Path | None) -> str:
    if path is None or not path.is_file():
        return "none"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _svc_id(service: dict[str, Any]) -> str:
    return f"{service.get('host') or ''}/{service.get('name') or service.get('key') or ''}"


def _render_context(desired: dict[str, Any]) -> dict[str, Any]:
    """Inputs substituted into Quadlets. A homepage edit does not change this."""
    p = policy(desired)
    return {
        "env": env(desired),
        "roots": roots(desired),
        "generate_upstream": p["generate_upstream"],
        "hosts": [
            {
                "name": h.get("name"),
                "ip": h.get("ip"),
                "env": h.get("env") or {},
                "roots": ((h.get("data") or {}).get("roots") or {}),
                "gpu": ((h.get("resources") or {}).get("gpu") or []),
                "user": ((h.get("operations") or {}).get("workload") or {}).get("user"),
            }
            for h in hosts(desired)
        ],
    }


def _edge_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for s in all_services(desired):
        rows.append(
            {
                "host": s.get("host"),
                "key": s.get("key"),
                "name": s.get("name"),
                "subdomain": s.get("subdomain"),
                "ports": s.get("ports"),
                "sso": s.get("sso"),
                "host_ip": s.get("host_ip"),
                "network": s.get("network"),
            }
        )
    return sorted(rows, key=lambda row: (row["host"] or "", row["name"] or ""))


def fingerprints(desired: dict[str, Any], secrets_path: Path | None = None) -> dict[str, Any]:
    """Stable hashes of each SET section and each placed service."""
    p = policy(desired)
    e = env(desired)
    context = _render_context(desired)
    trees: dict[str, str] = {}
    services: dict[str, dict[str, Any]] = {}
    for s in all_services(desired):
        component = str(s.get("component") or s.get("key") or "")
        if component not in trees:
            trees[component] = _tree_hash(COMPONENTS / component)
        rec = {
            "host": s.get("host") or "",
            "name": s.get("name") or s.get("key") or "",
            "key": s.get("key") or "",
            "privilege": s.get("privilege") or "rootless",
        }
        rec["hash"] = _digest(
            {
                "component": trees[component],
                "raw": s.get("raw") or {},
                "context": context,
                "subdomain": s.get("subdomain"),
                "ports": s.get("ports"),
                "sso": s.get("sso"),
            }
        )
        services[_svc_id(s)] = rec
    admin = [(h.get("name"), bool(h.get("admin-gui")), h.get("ip")) for h in hosts(desired)]
    sections = {
        "storage": _digest(
            {
                "roots": roots(desired),
                "hosts": [
                    {
                        "name": h.get("name"),
                        "data": h.get("data") or {},
                        "disks": (h.get("resources") or {}).get("disks"),
                        "storage": (h.get("operations") or {}).get("storage"),
                    }
                    for h in hosts(desired)
                ],
            }
        ),
        "imports": _digest({"blocks": import_blocks(desired), "nfs": import_nfs(desired)}),
        "ssh": _digest(
            {
                "ssh": p["ssh"],
                "hosts": [
                    {"name": h.get("name"), "users": h.get("users") or [], "identity": h.get("identity") or {}}
                    for h in hosts(desired)
                ],
            }
        ),
        "users": _digest({"users": site_of(desired).get("users") or [], "groups": site_groups(desired)}),
        "ldap": _digest({"ldap": p["ldap"], "placed": [i for i, rec in services.items() if rec["key"] == "openldap"]}),
        "drivers": _digest(
            [
                {
                    "name": h.get("name"),
                    "gpu": (h.get("resources") or {}).get("gpu"),
                    "usb": (h.get("resources") or {}).get("usb"),
                }
                for h in hosts(desired)
            ]
        ),
        "pwm": _digest([{"name": h.get("name"), "pwm": (h.get("resources") or {}).get("pwm")} for h in hosts(desired)]),
        "admin_gui": _digest({"domain": e.get("domain"), "hosts": admin}),
        "podman": _digest(
            {
                "engine": p["workload_engine"],
                "users": [
                    {
                        "name": h.get("name"),
                        "user": ((h.get("operations") or {}).get("workload") or {}).get("user"),
                    }
                    for h in hosts(desired)
                ],
            }
        ),
        "secrets": _file_hash(secrets_path),
        "nfs": _digest(inferred_nfs(desired)),
        "edge": _digest(
            {
                "generate_upstream": p["generate_upstream"],
                "ingress": p["ingress"],
                "domain": e.get("domain"),
                "lan_ip": e.get("lan_ip"),
                "admin_gui": admin,
                "services": _edge_services(desired),
            }
        ),
        "opencloud": _digest([rec for rec in services.values() if rec["key"] == "opencloud"]),
        "lan_bind": _digest([rec for rec in services.values() if rec["key"] in ("caddy", "pi-hole")]),
        "static_ip": _digest([(h.get("name"), h.get("ip")) for h in hosts(desired)]),
        "quadlets": _digest(sorted(services)),
    }
    return {"sections": sections, "services": services}


def _records(services: dict[str, Any], ids: set[str]) -> list[dict[str, Any]]:
    return [services[i] for i in sorted(ids)]


def set_delta(
    desired: dict[str, Any],
    applied: dict[str, Any] | None,
    secrets_path: Path | None = None,
    *,
    full: bool = False,
    upgrade: bool = False,
) -> dict[str, Any]:
    """What this SET must touch. `applied` is the fingerprint file from the previous SET."""
    fps = fingerprints(desired, secrets_path)
    section_names = list(fps["sections"])
    if full or not isinstance(applied, dict) or "sections" not in applied:
        if full or not upgrade:
            sections = {name: True for name in section_names}
            return {
                "full": True,
                "sync_all": True,
                "sections": sections,
                "services": {"add": [], "remove": [], "change": _records(fps["services"], set(fps["services"]))},
                "users": {"add": [], "remove": []},
                "fingerprints": fps,
            }
        sections = {name: name in UPGRADE_SECTIONS for name in section_names}
        return {
            "full": False,
            "sync_all": True,
            "sections": sections,
            "services": {"add": [], "remove": [], "change": []},
            "users": {"add": [], "remove": []},
            "fingerprints": fps,
        }
    old_sections = applied.get("sections") or {}
    old_services = applied.get("services") or {}
    if not isinstance(old_services, dict):
        old_services = {}
    sections = {name: old_sections.get(name) != fps["sections"][name] for name in section_names}
    new_ids = set(fps["services"])
    old_ids = set(old_services)
    add = _records(fps["services"], new_ids - old_ids)
    remove = [old_services[i] for i in sorted(old_ids - new_ids) if isinstance(old_services.get(i), dict)]
    change = [
        fps["services"][i]
        for i in sorted(new_ids & old_ids)
        if (old_services.get(i) or {}).get("hash") != fps["services"][i].get("hash")
    ]
    if sections["edge"]:
        present = {rec["host"] + "/" + rec["name"] for rec in change + add}
        for rec in fps["services"].values():
            if rec["key"] in ("caddy", "authelia") and f"{rec['host']}/{rec['name']}" not in present:
                change.append(rec)
    bind_keys = ("caddy", "pi-hole")
    if sections["edge"] or any(rec.get("key") in bind_keys for rec in add + change + remove):
        sections["lan_bind"] = True
    sections["quadlets"] = bool(add or change or remove)
    return {
        "full": False,
        "sync_all": False,
        "sections": sections,
        "services": {"add": add, "remove": remove, "change": change},
        "users": {"add": [], "remove": []},
        "fingerprints": fps,
    }
