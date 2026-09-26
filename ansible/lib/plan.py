"""Build the SET plan consumed by playbooks (NFS, dirs, imports, policy)."""
from __future__ import annotations

from typing import Any

from .topology import (
    all_services,
    hosts,
    policy,
    root_owners,
    roots,
    site_of,
)

# Services that consume people roots (users / groups) off-host → inferred NFS.
PEOPLE_ROOT_KEYS = {
    "opencloud",
    "immich",
    "jellyfin",
    "arr",
    "qbittorrent",
    "frigate",
    "seerr",
}


def workload_user(desired: dict[str, Any], host_name: str) -> str:
    for h in hosts(desired):
        if h.get("name") == host_name:
            wl = (h.get("roles") or {}).get("workload") or {}
            return str(wl.get("user") or "")
    return ""


def inferred_nfs(desired: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Export a root only when a placed service consumes it on another host."""
    owners = root_owners(desired)
    exports: list[dict[str, str]] = []
    mounts: list[dict[str, str]] = []
    seen_ex: set[tuple] = set()
    seen_mnt: set[tuple] = set()
    for s in all_services(desired):
        consumer = s.get("host") or ""
        consumer_ip = s.get("host_ip") or ""
        consumed = ["appdata"]
        if s.get("key") in PEOPLE_ROOT_KEYS:
            consumed.extend(["groups", "users"])
        for root in consumed:
            owner = owners.get(root)
            if not owner or not owner.get("host"):
                continue
            if owner["host"] == consumer:
                continue
            path = owner["path"]
            ex_key = (owner["host"], path, consumer_ip)
            if ex_key not in seen_ex:
                seen_ex.add(ex_key)
                exports.append(
                    {
                        "host": owner["host"],
                        "path": path,
                        "client_ip": consumer_ip,
                        "workload_user": workload_user(desired, consumer),
                    }
                )
            mnt_key = (consumer, path, owner["host_ip"])
            if mnt_key not in seen_mnt:
                seen_mnt.add(mnt_key)
                mounts.append(
                    {
                        "host": consumer,
                        "path": path,
                        "server_ip": owner["host_ip"],
                        "export": path,
                    }
                )
    return {"exports": exports, "mounts": mounts}


def service_dirs(desired: dict[str, Any]) -> list[dict[str, str]]:
    """Create groups/all/<dir> only when an official service that needs it is listed."""
    owners = root_owners(desired)
    groups = owners.get("groups")
    if not groups:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for s in all_services(desired):
        for d in s.get("dirs") or []:
            if d in seen:
                continue
            seen.add(d)
            out.append(
                {
                    "host": groups["host"],
                    "path": f"{groups['path']}/all/{d}",
                }
            )
    return out


def import_blocks(desired: dict[str, Any]) -> list[dict[str, Any]]:
    r = roots(desired)
    generated = {"Caddyfile", "configuration.yml", "configuration.yaml"}
    blocks = []
    for h in hosts(desired):
        for disk in ((h.get("resources") or {}).get("disks") or []):
            imp = disk.get("import") or {}
            if not imp:
                continue
            # mapping: {from_path: to_hint} or {trees: [{from, to}]}
            trees = imp.get("trees") or []
            if not trees and isinstance(imp, dict):
                for src, dest in imp.items():
                    if src in ("trees", "stamp"):
                        continue
                    trees.append({"from": src, "to": dest})
            for t in trees:
                dest = str(t.get("to") or "")
                if dest in ("all", "/all"):
                    dest = f"{r['groups']}/all"
                elif dest in ("appdata", "system"):
                    dest = r["appdata"]
                elif dest in ("users",):
                    dest = r["users"]
                name = dest.rsplit("/", 1)[-1]
                blocks.append(
                    {
                        "host": h.get("name"),
                        "disk": disk.get("id"),
                        "from": t.get("from"),
                        "to": dest,
                        "generated": name in generated or dest.endswith(tuple(generated)),
                    }
                )
    return blocks


def site_groups(desired: dict[str, Any]) -> list[str]:
    names = {"all"}
    for u in site_of(desired).get("users") or []:
        for g in u.get("groups") or []:
            names.add(g)
    return sorted(names)


def build_plan(desired: dict[str, Any]) -> dict[str, Any]:
    nfs = inferred_nfs(desired)
    p = policy(desired)
    return {
        "policy": p,
        "roots": roots(desired),
        "owners": root_owners(desired),
        "services": all_services(desired),
        "nfs_exports": nfs["exports"],
        "nfs_mounts": nfs["mounts"],
        "service_dirs": service_dirs(desired),
        "imports": import_blocks(desired),
        "users": site_of(desired).get("users") or [],
        "groups": site_groups(desired),
        "hosts": hosts(desired),
        "cockpit": p["host_manager"] == "cockpit",
        "glances_implicit": p["host_monitor"] == "glances",
        "ldap": p["ldap"],
        "sso_backend": "ldap" if p["ldap"] == "openldap" else "file",
    }
