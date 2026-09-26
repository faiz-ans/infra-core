"""Load desired topology, pack metadata, and placement helpers."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "components" / "pack.yaml"

SITE_USER_ROLES = {"sysadmin", "sysuser", "appadmin", "appuser"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data


def load_pack() -> dict[str, Any]:
    return load_yaml(PACK_PATH)


def load_desired(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    if "site" not in data:
        raise ValueError(f"{path} must have a top-level 'site' key")
    return data


def site_of(desired: dict[str, Any]) -> dict[str, Any]:
    return desired.get("site") or {}


def hosts(desired: dict[str, Any]) -> list[dict[str, Any]]:
    return list(site_of(desired).get("hosts") or [])


def host_by_name(desired: dict[str, Any], name: str) -> dict[str, Any] | None:
    for h in hosts(desired):
        if h.get("name") == name:
            return h
    return None


def env(desired: dict[str, Any]) -> dict[str, Any]:
    return dict(site_of(desired).get("env") or {})


def roots(desired: dict[str, Any]) -> dict[str, str]:
    raw = (site_of(desired).get("data") or {}).get("roots") or {}
    return {
        "appdata": raw.get("appdata", "/appdata"),
        "groups": raw.get("groups", "/groups"),
        "users": raw.get("users", "/users"),
    }


def policy(desired: dict[str, Any]) -> dict[str, Any]:
    s = site_of(desired)
    net = s.get("networking") or {}
    ident = s.get("identity") or {}
    ops = s.get("operations") or {}
    data = s.get("data") or {}
    access = data.get("access") or {}
    tunnel = net.get("tunnel") or {}
    return {
        "dns": net.get("dns") or "none",
        "ingress": net.get("ingress") or "none",
        "tunnel": tunnel.get("engine") or "none",
        "tunnel_endpoint": tunnel.get("endpoint") or "",
        "ldap": ident.get("ldap") or "none",
        "sso": ident.get("sso") or "none",
        "ssh": str(ident.get("ssh") or "false"),
        "host_manager": (ops.get("host") or {}).get("manager") or "none",
        "host_monitor": (ops.get("host") or {}).get("monitor") or "none",
        "storage_engine": (ops.get("storage") or {}).get("engine") or "native",
        "storage_monitor": (ops.get("storage") or {}).get("monitor") or "none",
        "workload_engine": (ops.get("workload") or {}).get("engine") or "podman",
        "workload_monitor": (ops.get("workload") or {}).get("monitor") or "none",
        "filesystem": access.get("filesystem") or "smb",
        "web": access.get("web") or "none",
    }


def listed_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten hosts[].roles.workload.services into instance records."""
    pack = load_pack().get("services") or {}
    out: list[dict[str, Any]] = []
    for h in hosts(desired):
        wl = ((h.get("roles") or {}).get("workload") or {})
        services = wl.get("services") or {}
        for key, val in services.items():
            instances = val if isinstance(val, list) else [val or {}]
            if instances == [None]:
                instances = [{}]
            for inst in instances:
                inst = inst or {}
                name = inst.get("name") or key
                meta = copy.deepcopy(pack.get(key) or pack.get(name) or {})
                sub = inst.get("subdomain") or meta.get("subdomain") or {}
                out.append(
                    {
                        "host": h.get("name"),
                        "host_ip": h.get("ip"),
                        "key": key,
                        "name": name,
                        "component": meta.get("component") or key.replace("-", ""),
                        "sso": inst.get("sso") or meta.get("sso") or "forward-auth",
                        "tile": inst.get("tile", meta.get("tile", True)),
                        "network": meta.get("network") or "site",
                        "privilege": meta.get("privilege") or "rootless",
                        "subdomain": sub,
                        "keep_id": bool(meta.get("keep_id")),
                        "dirs": list(meta.get("dirs") or []),
                        "publish": list(meta.get("publish") or []),
                        "ports": dict(meta.get("ports") or {}),
                        "raw": inst,
                    }
                )
    return out


def implicit_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    """Cockpit is a host package. Glances is implicit on every workload host."""
    p = policy(desired)
    have = {(s["host"], s["key"]) for s in listed_services(desired)}
    extra: list[dict[str, Any]] = []
    if p["host_monitor"] == "glances":
        for h in hosts(desired):
            if not (h.get("roles") or {}).get("workload"):
                continue
            if (h.get("name"), "glances") in have:
                continue
            extra.append(
                {
                    "host": h.get("name"),
                    "host_ip": h.get("ip"),
                    "key": "glances",
                    "name": "glances",
                    "component": "glances",
                    "sso": "forward-auth",
                    "tile": True,
                    "network": "site",
                    "privilege": "rootless",
                    "subdomain": {"primary": "host", "aliases": ["glances"]},
                    "keep_id": False,
                    "dirs": [],
                    "publish": [],
                    "ports": {},
                    "raw": {"implicit": True},
                }
            )
    return extra


def all_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    return listed_services(desired) + implicit_services(desired)


def root_owners(desired: dict[str, Any]) -> dict[str, dict[str, str]]:
    """root name -> {host, drive, path}."""
    r = roots(desired)
    owners: dict[str, dict[str, str]] = {}
    for h in hosts(desired):
        storage = ((h.get("roles") or {}).get("storage") or {})
        for drive in storage.get("drives") or []:
            for root in drive.get("roots") or []:
                owners[root] = {
                    "host": h.get("name") or "",
                    "host_ip": h.get("ip") or "",
                    "drive": drive.get("id") or "",
                    "path": r[root],
                }
    return owners


def storage_hosts(desired: dict[str, Any]) -> list[str]:
    names = []
    for h in hosts(desired):
        if (h.get("roles") or {}).get("storage"):
            names.append(h.get("name"))
    return names


def owners_of_people_roots(desired: dict[str, Any]) -> list[str]:
    owners = root_owners(desired)
    names = []
    for key in ("groups", "users"):
        if key in owners and owners[key]["host"] not in names:
            names.append(owners[key]["host"])
    return names


def placed_keys(desired: dict[str, Any]) -> set[str]:
    return {s["key"] for s in all_services(desired)}


def validate_placement(desired: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    p = policy(desired)
    placed = placed_keys(desired)
    engine_map = {
        "dns": (p["dns"], "pi-hole"),
        "ingress": (p["ingress"], "caddy"),
        "sso": (p["sso"], "authelia"),
        "ldap": (p["ldap"], "openldap"),
        "web": (p["web"], "opencloud"),
        "storage.monitor": (p["storage_monitor"], "scrutiny"),
        "workload.monitor": (p["workload_monitor"], "uptime-kuma"),
        "tunnel": (p["tunnel"], "wireguard"),
    }
    for label, (engine, key) in engine_map.items():
        if engine in (None, "", "none"):
            continue
        if engine != key.split("-")[0] and engine != key and engine != key.replace("-", ""):
            # allow dns: pi-hole matching key pi-hole
            pass
        want = key if engine in (key, key.replace("-", ""), engine) else engine
        aliases = {want, want.replace("_", "-"), "pi-hole" if want in ("pihole", "pi-hole") else want}
        if label == "dns":
            aliases.update({"pi-hole", "pihole"})
        if label == "ldap":
            aliases.add("openldap")
        if not aliases.intersection(placed) and label != "host.manager":
            if label == "ldap" and p["ldap"] == "openldap" and "openldap" not in placed:
                errors.append("identity.ldap is openldap but no workload lists openldap")
            elif label == "dns" and p["dns"] in ("pi-hole", "pihole") and not {"pi-hole", "pihole"} & placed:
                errors.append("networking.dns is pi-hole but no workload lists pi-hole")
            elif label == "ingress" and p["ingress"] == "caddy" and "caddy" not in placed:
                errors.append("networking.ingress is caddy but no workload lists caddy")
            elif label == "sso" and p["sso"] == "authelia" and "authelia" not in placed:
                errors.append("identity.sso is authelia but no workload lists authelia")
            elif label == "web" and p["web"] == "opencloud" and "opencloud" not in placed:
                errors.append("data.access.web is opencloud but no workload lists opencloud")
            elif label == "storage.monitor" and p["storage_monitor"] == "scrutiny" and "scrutiny" not in placed:
                errors.append("operations.storage.monitor is scrutiny but no workload lists scrutiny")
            elif label == "workload.monitor" and p["workload_monitor"] == "uptime-kuma" and "uptime-kuma" not in placed:
                errors.append("operations.workload.monitor is uptime-kuma but no workload lists uptime-kuma")
            elif label == "tunnel" and p["tunnel"] == "wireguard" and not {"wireguard", "wireguard-data"} & placed:
                errors.append("networking.tunnel.engine is wireguard but no workload lists wireguard")
    ingress_hosts = [s["host"] for s in all_services(desired) if s["key"] == "caddy"]
    if p["ingress"] == "caddy" and len(set(ingress_hosts)) > 1:
        errors.append("networking.ingress is caddy but more than one host lists caddy")
    for h in hosts(desired):
        locals_ = h.get("users") or []
        if not any("sysadmin" in (u.get("roles") or []) for u in locals_):
            errors.append(f"host {h.get('name')} has no local sysadmin")
    return errors


def key_only_ready(desired: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    p = policy(desired)
    for h in hosts(desired):
        override = ((h.get("override") or {}).get("identity") or {})
        ssh = str(override.get("ssh") or p["ssh"])
        if ssh != "key-only":
            continue
        admins = [u for u in (h.get("users") or []) if "sysadmin" in (u.get("roles") or [])]
        if not any(u.get("ssh-keys") for u in admins):
            errors.append(f"identity.ssh is key-only on {h.get('name')} but no sysadmin has ssh-keys")
    return errors


def ingress_host(desired: dict[str, Any]) -> dict[str, str] | None:
    for s in all_services(desired):
        if s["key"] == "caddy":
            return {"name": s["host"], "ip": s["host_ip"] or ""}
    return None
