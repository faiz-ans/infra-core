"""Load desired topology, pack metadata, and placement helpers."""
from __future__ import annotations

import copy
import posixpath
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


def _engine_name(raw: Any, default: str = "none") -> str:
    if isinstance(raw, dict):
        return str(raw.get("engine") or default)
    if raw in (None, ""):
        return default
    return str(raw)


INGRESS_PLUGINS = {"sablier"}


def _exception_label(item: Any) -> str:
    if isinstance(item, str):
        return item
    return repr(item)


def _one_pair(item: Any) -> tuple[str, Any] | None:
    if not isinstance(item, dict) or len(item) != 1:
        return None
    key, value = next(iter(item.items()))
    return str(key), value


def _parse_exception(item: Any) -> tuple[dict[str, Any] | None, str | None]:
    """One forward-auth exception.

    A string is a service key (every instance on the site) or a route label.
    ``inst`` is an instance name, never a host. A host key narrows the match
    to that host, and a nested user key narrows it again.
    """
    label = _exception_label(item)
    blank: dict[str, Any] = {"host": None, "user": None, "service": None, "instance": None, "label": label}
    if isinstance(item, str):
        if not item:
            return None, f"networking.ingress.forward-auth.exceptions entry {label!r} is empty"
        return {**blank, "service": item}, None
    pair = _one_pair(item)
    if pair is None:
        return None, (
            f"networking.ingress.forward-auth.exceptions entry {label} "
            "must be a service, an instance, or a single host scope"
        )
    key, value = pair
    if key == "inst":
        if not isinstance(value, str) or not value:
            return None, f"networking.ingress.forward-auth.exceptions entry {label} needs an instance name"
        return {**blank, "instance": value}, None
    if isinstance(value, str) and value:
        return {**blank, "host": key, "service": value}, None
    inner = _one_pair(value)
    if inner is None:
        return None, (
            f"networking.ingress.forward-auth.exceptions entry {label} "
            "must name a service, an instance, or one user"
        )
    inner_key, inner_value = inner
    if inner_key == "inst":
        if not isinstance(inner_value, str) or not inner_value:
            return None, f"networking.ingress.forward-auth.exceptions entry {label} needs an instance name"
        return {**blank, "host": key, "instance": inner_value}, None
    if isinstance(inner_value, str) and inner_value:
        return {**blank, "host": key, "user": inner_key, "service": inner_value}, None
    inst = _one_pair(inner_value)
    if inst and inst[0] == "inst" and isinstance(inst[1], str) and inst[1]:
        return {**blank, "host": key, "user": inner_key, "instance": inst[1]}, None
    return None, (
        f"networking.ingress.forward-auth.exceptions entry {label} "
        "must name a service or an instance for that user"
    )


def _forward_auth(ingress: Any) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """Opt-in gate. Exceptions are ignored until enabled, but still checked."""
    if not isinstance(ingress, dict):
        return False, [], []
    block = ingress.get("forward-auth", ingress.get("forward_auth", {}))
    if block is None:
        block = {}
    errors: list[str] = []
    if "auth-exceptions" in ingress or "auth_exceptions" in ingress:
        errors.append(
            "networking.ingress auth-exceptions moved to ingress.forward-auth.exceptions"
        )
    if not isinstance(block, dict):
        errors.append("networking.ingress.forward-auth must be a mapping")
        return False, [], errors
    enabled = bool(block.get("enabled", False))
    raw = block.get("exceptions") or []
    if isinstance(raw, (str, dict)):
        raw = [raw]
    if not isinstance(raw, list):
        errors.append("networking.ingress.forward-auth.exceptions must be a list")
        return enabled, [], errors
    rules: list[dict[str, Any]] = []
    for item in raw:
        rule, error = _parse_exception(item)
        if error:
            errors.append(error)
        elif rule:
            rules.append(rule)
    return enabled, rules, errors


def _plugins(ingress: Any) -> tuple[list[str], list[str]]:
    if not isinstance(ingress, dict) or "plugins" not in ingress:
        return [], []
    raw = ingress.get("plugins")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return [], ["networking.ingress.plugins must be a list"]
    errors: list[str] = []
    names: list[str] = []
    for item in raw:
        name = str(item or "")
        if not name:
            errors.append("networking.ingress.plugins has an empty entry")
            continue
        if name not in INGRESS_PLUGINS:
            errors.append(f"networking.ingress.plugins entry {name!r} is not supported")
            continue
        if name not in names:
            names.append(name)
    return names, errors


def _flag(raw: Any, key: str, default: bool = True) -> bool:
    if not isinstance(raw, dict) or key not in raw:
        alt = key.replace("-", "_")
        if isinstance(raw, dict) and alt in raw:
            return bool(raw[alt])
        return default
    return bool(raw[key])


def _portal_assets(ingress: Any) -> str:
    """Operator directory for the Authelia login page. Empty means no injection."""
    if not isinstance(ingress, dict):
        return ""
    raw = ingress.get("portal-assets", ingress.get("portal_assets", ""))
    if raw is None:
        return ""
    return str(raw).strip()


def policy(desired: dict[str, Any]) -> dict[str, Any]:
    s = site_of(desired)
    net = s.get("networking") or {}
    ident = s.get("identity") or {}
    ops = s.get("operations") or {}
    data = s.get("data") or {}
    access = data.get("access") or {}
    tunnel = net.get("tunnel") or {}
    ingress = net.get("ingress")
    forward_auth, auth_exceptions, _forward_errors = _forward_auth(ingress)
    plugins, _plugin_errors = _plugins(ingress)
    return {
        "dns": net.get("dns") or "none",
        "ingress": _engine_name(ingress),
        "generate_upstream": _flag(ingress, "generate-upstream", True),
        "forward_auth": forward_auth,
        "auth_exceptions": auth_exceptions,
        "plugins": plugins,
        "portal_assets": _portal_assets(ingress),
        "tunnel": tunnel.get("engine") or "none",
        "tunnel_endpoint": tunnel.get("endpoint") or "",
        "ldap": ident.get("ldap") or "none",
        "sso": ident.get("sso") or "none",
        "ssh": str(ident.get("ssh") or "false"),
        "storage_engine": (ops.get("storage") or {}).get("engine") or "native",
        "storage_monitor": (ops.get("storage") or {}).get("monitor") or "none",
        "workload_engine": (ops.get("workload") or {}).get("engine") or "podman",
        "workload_monitor": (ops.get("workload") or {}).get("monitor") or "none",
        "filesystem": access.get("filesystem") or "smb",
        "web": access.get("web") or "none",
    }


def service_subdomain(key: str, custom: Any) -> dict[str, Any]:
    """The service name is the host label. A site.yaml subdomain replaces it."""
    custom = custom if isinstance(custom, dict) else {}
    primary = str(custom.get("primary") or key)
    aliases = [str(alias) for alias in (custom.get("aliases") or [])]
    return {"primary": primary, "aliases": aliases}


def admin_gui(value: Any) -> dict[str, Any]:
    """Normalize hosts[].admin-gui. Boolean true keeps the cockpit host label."""
    if value is True:
        return {"enabled": True, "primary": "cockpit", "aliases": []}
    if isinstance(value, dict):
        enabled = value.get("enabled")
        return {
            "enabled": bool(enabled if enabled is not None else True),
            "primary": str(value.get("primary") or "cockpit"),
            "aliases": [str(alias) for alias in (value.get("aliases") or [])],
        }
    return {"enabled": False, "primary": "cockpit", "aliases": []}


def workload_users(host: dict[str, Any]) -> list[dict[str, Any]]:
    """Named local accounts under this host's workload, each with its own services."""
    wl = (host.get("operations") or {}).get("workload") or {}
    raw = wl.get("users") if isinstance(wl, dict) else None
    if not isinstance(raw, list):
        return []
    return [user for user in raw if isinstance(user, dict)]


def _instance_name(key: str, inst: dict[str, Any], taken: set[str]) -> str:
    """Use the name in site.yaml. Otherwise key, key2, key3, skipping names already used."""
    explicit = str(inst.get("name") or "")
    if explicit:
        return explicit
    number = 1
    while True:
        candidate = key if number == 1 else f"{key}{number}"
        if candidate not in taken:
            return candidate
        number += 1


def listed_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten each workload user's services into instance records."""
    pack = load_pack().get("services") or {}
    out: list[dict[str, Any]] = []
    for h in hosts(desired):
        for entry in workload_users(h):
            user = str(entry.get("name") or "")
            taken: set[str] = set()
            services = entry.get("services") or {}
            if not isinstance(services, dict):
                continue
            for key, val in services.items():
                instances = val if isinstance(val, list) else [val or {}]
                if instances == [None]:
                    instances = [{}]
                for inst in instances:
                    inst = inst or {}
                    name = _instance_name(str(key), inst, taken)
                    taken.add(name)
                    meta = copy.deepcopy(pack.get(key) or pack.get(name) or {})
                    out.append(
                        {
                            "host": h.get("name"),
                            "host_ip": h.get("ip"),
                            "user": user,
                            "key": key,
                            "name": name,
                            "component": meta.get("component") or key,
                            "sso": inst.get("sso") or meta.get("sso") or "forward-auth",
                            "network": meta.get("network") or "site",
                            "privilege": meta.get("privilege") or "rootless",
                            "subdomain": service_subdomain(name, inst.get("subdomain")),
                            "keep_id": bool(meta.get("keep_id")),
                            "dirs": list(meta.get("dirs") or []),
                            "publish": list(meta.get("publish") or []),
                            "ports": dict(meta.get("ports") or {}),
                            "raw": inst,
                        }
                    )
    return _with_scrutiny_collector(out, pack)


def _with_scrutiny_collector(services: list[dict[str, Any]], pack: dict[str, Any]) -> list[dict[str, Any]]:
    """SMART needs ATA pass-through, which a rootless container cannot do."""
    if any(rec.get("key") == "scrutiny-collector" for rec in services):
        return services
    meta = pack.get("scrutiny-collector") or {}
    extra: list[dict[str, Any]] = []
    for rec in services:
        if rec.get("key") != "scrutiny":
            continue
        extra.append(
            {
                "host": rec.get("host"),
                "host_ip": rec.get("host_ip"),
                "key": "scrutiny-collector",
                "name": "scrutiny-collector",
                "component": meta.get("component") or "scrutiny-collector",
                "user": rec.get("user") or "",
                "sso": "none",
                "network": meta.get("network") or "host",
                "privilege": meta.get("privilege") or "rootful",
                "subdomain": {"primary": "", "aliases": []},
                "keep_id": False,
                "dirs": [],
                "publish": [],
                "ports": {},
                "raw": {},
            }
        )
    return services + extra


def all_services(desired: dict[str, Any]) -> list[dict[str, Any]]:
    return listed_services(desired)


def root_owners(desired: dict[str, Any]) -> dict[str, dict[str, str]]:
    """root name -> {host, drive, path}."""
    r = roots(desired)
    owners: dict[str, dict[str, str]] = {}
    for h in hosts(desired):
        storage = ((h.get("operations") or {}).get("storage") or {})
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
        if (h.get("operations") or {}).get("storage"):
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


def host_user_is_sysadmin(user: dict[str, Any]) -> bool:
    """Host user administers the machine via sysadmin: true or roles: [sysadmin]."""
    if user.get("sysadmin") is True:
        return True
    return "sysadmin" in (user.get("roles") or [])


def host_roots(host: dict[str, Any]) -> dict[str, str]:
    data = host.get("data") or {}
    raw = data.get("roots") if isinstance(data, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if k}


def site_roots_mounted_on(desired: dict[str, Any], host: dict[str, Any]) -> dict[str, str]:
    """Site root name → path, for roots this host's storage drives mount."""
    declared = roots(desired)
    mounted: dict[str, str] = {}
    for drive in (((host.get("operations") or {}).get("storage") or {}).get("drives") or []):
        for root in drive.get("roots") or []:
            if root in declared:
                mounted[str(root)] = posixpath.normpath(str(declared[root]))
    return mounted


def shared_host_roots(desired: dict[str, Any], host: dict[str, Any]) -> set[str]:
    """Host-root keys listed on a storage volume whose path is a site root that volume mounts.

    The key name is not special. A matching path shares that directory; any other path is a normal host root.
    """
    declared = roots(desired)
    drive_paths: dict[str, set[str]] = {}
    for drive in (((host.get("operations") or {}).get("storage") or {}).get("drives") or []):
        ident = str(drive.get("id") or "")
        paths: set[str] = set()
        for root in drive.get("roots") or []:
            if root in declared:
                paths.add(posixpath.normpath(str(declared[root])))
        if ident:
            drive_paths[ident] = paths
    written = host_roots(host)
    shared: set[str] = set()
    for vol in host_volumes(host):
        paths = drive_paths.get(str(vol.get("id") or ""))
        if not paths:
            continue
        for root in volume_host_roots(vol):
            path = written.get(root)
            if path and posixpath.normpath(path) in paths:
                shared.add(root)
    return shared


def volume_host_roots(volume: dict[str, Any]) -> list[str]:
    """Host-root names this disk or partition owns. `roots` is a list here, not the host path map."""
    raw = volume.get("roots")
    if isinstance(raw, list):
        return [str(r) for r in raw]
    return [str(r) for r in (volume.get("local-roots") or volume.get("local_roots") or [])]


def host_volumes(host: dict[str, Any]) -> list[dict[str, Any]]:
    """Partition when the disk has any; otherwise the disk. Partitions inherit internal from the disk."""
    out: list[dict[str, Any]] = []
    for disk in (host.get("resources") or {}).get("disks") or []:
        if not isinstance(disk, dict):
            continue
        parts = [p for p in (disk.get("partitions") or []) if isinstance(p, dict)]
        if parts:
            for part in parts:
                vol = dict(part)
                if disk.get("internal") and "internal" not in part:
                    vol["internal"] = True
                out.append(vol)
        else:
            out.append(disk)
    return out


def validate_local_roots(desired: dict[str, Any]) -> list[str]:
    """Every host root is owned once. A storage drive may share one only when the path is the site root it already mounts."""
    errors: list[str] = []
    storage_ids: set[str] = set()
    for h in hosts(desired):
        for drive in (((h.get("operations") or {}).get("storage") or {}).get("drives") or []):
            ident = drive.get("id")
            if ident:
                storage_ids.add(str(ident))
    for h in hosts(desired):
        name = h.get("name") or "host"
        declared = host_roots(h)
        shared = shared_host_roots(desired, h)
        mounted_paths = set(site_roots_mounted_on(desired, h).values())
        owned: list[str] = []
        for vol in host_volumes(h):
            locals_ = volume_host_roots(vol)
            if not locals_:
                continue
            did = str(vol.get("id") or "")
            shares_storage = did in storage_ids
            if shares_storage and any(root not in shared for root in locals_):
                errors.append(
                    f"disk {did!r} owns local-roots but is also listed as a storage drive"
                )
            for root in locals_:
                if root not in declared:
                    errors.append(
                        f"host {name} disk {did} local-root {root!r} is not in host roots"
                    )
                    continue
                path = declared[root]
                if not path.startswith("/"):
                    errors.append(f"host {name} roots.{root} must be an absolute path")
                elif (
                    not shares_storage
                    and posixpath.normpath(path) in mounted_paths
                ):
                    errors.append(
                        f"host {name} roots.{root} uses a site root path this host already mounts; list it on that storage volume"
                    )
                owned.append(root)
        if len(owned) != len(set(owned)):
            errors.append(f"host {name} has a local-root owned by more than one disk")
        for root, path in declared.items():
            if root not in owned:
                errors.append(f"host {name} roots.{root} is not owned by any disk local-roots")
            elif path and not str(path).startswith("/"):
                errors.append(f"host {name} roots.{root} must be an absolute path")
    return errors


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
        want = key if engine == key else engine
        aliases = {want, want.replace("_", "-")}
        if label == "ldap":
            aliases.add("openldap")
        if not aliases.intersection(placed):
            if label == "ldap" and p["ldap"] == "openldap" and "openldap" not in placed:
                errors.append("identity.ldap is openldap but no workload lists openldap")
            elif label == "dns" and p["dns"] == "pi-hole" and "pi-hole" not in placed:
                errors.append("networking.dns is pi-hole but no workload lists pi-hole")
            elif label == "dns" and p["dns"] != "pi-hole":
                errors.append(f"networking.dns is {p['dns']} but the service name is pi-hole")
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
        if not any(host_user_is_sysadmin(u) for u in locals_):
            errors.append(f"host {h.get('name')} has no local sysadmin")
    errors.extend(validate_local_roots(desired))
    errors.extend(validate_workload_users(desired))
    errors.extend(validate_ingress(desired))
    from .plan import nfs_user_conflicts

    errors.extend(nfs_user_conflicts(desired))
    from .backup import validate_backup

    errors.extend(validate_backup(desired))
    from .pwm import validate_pwm

    errors.extend(validate_pwm(desired))
    return errors


def local_account_names(host: dict[str, Any]) -> set[str]:
    return {str(user.get("name")) for user in (host.get("users") or []) if user.get("name")}


def validate_workload_users(desired: dict[str, Any]) -> list[str]:
    """Each workload user is a local account."""
    errors: list[str] = []
    for host in hosts(desired):
        name = host.get("name") or "host"
        wl = (host.get("operations") or {}).get("workload") or {}
        if not isinstance(wl, dict):
            continue
        if "user" in wl or "services" in wl:
            errors.append(
                f"host {name} workload lists one user and one service map; use workload.users, each with a name and services"
            )
        seen_users: set[str] = set()
        accounts = local_account_names(host)
        for entry in workload_users(host):
            user = str(entry.get("name") or "")
            if not user:
                errors.append(f"host {name} has a workload user with no name")
                continue
            if user in seen_users:
                errors.append(f"host {name} lists workload user {user} more than once")
            seen_users.add(user)
            if user not in accounts:
                errors.append(f"host {name} workload user {user} is not a local account")
            services = entry.get("services") or {}
            if not isinstance(services, dict):
                errors.append(f"host {name} workload user {user} services must be a mapping")
    return errors


def route_labels(desired: dict[str, Any]) -> set[str]:
    """Cockpit labels and the router site. These are not workload services."""
    tokens = {"wifi"}
    for host in hosts(desired):
        gui = admin_gui(host.get("admin-gui"))
        if not gui["enabled"]:
            continue
        tokens.add(gui["primary"])
        tokens.update(alias for alias in gui["aliases"] if alias)
    return tokens


def exception_covers_service(rule: dict[str, Any], service: dict[str, Any]) -> bool:
    """True when this forward-auth exception skips the gate for one instance."""
    if rule.get("host") and rule["host"] != service.get("host"):
        return False
    if rule.get("user") and rule["user"] != service.get("user"):
        return False
    if rule.get("instance"):
        return rule["instance"] == service.get("name")
    if rule.get("service"):
        return rule["service"] == service.get("key")
    return False


def exception_covers_route(rule: dict[str, Any], *tokens: str) -> bool:
    """A bare service-or-route name can also skip Cockpit or the router site."""
    if rule.get("host") or rule.get("user") or rule.get("instance"):
        return False
    service = rule.get("service")
    return bool(service and service in tokens)


def validate_ingress(desired: dict[str, Any]) -> list[str]:
    """Forward-auth is opt-in. Plugins integrate only when listed and placed."""
    s = site_of(desired)
    ingress = (s.get("networking") or {}).get("ingress")
    _enabled, _rules, errors = _forward_auth(ingress)
    _names, plugin_errors = _plugins(ingress)
    errors.extend(plugin_errors)
    assets = _portal_assets(ingress)
    if assets and any(char.isspace() for char in assets):
        errors.append("networking.ingress.portal-assets must be a path without spaces")
    p = policy(desired)
    placed = placed_keys(desired)
    services = all_services(desired)
    if p["forward_auth"]:
        if p["ingress"] != "caddy":
            errors.append("ingress.forward-auth.enabled requires networking.ingress.engine caddy")
        if p["sso"] in (None, "", "none"):
            errors.append("ingress.forward-auth.enabled requires identity.sso")
        elif p["sso"] != "authelia":
            errors.append(
                f"ingress.forward-auth.enabled requires identity.sso authelia, not {p['sso']}"
            )
        elif "authelia" not in placed:
            errors.append("ingress.forward-auth.enabled requires a placed authelia service")
    keys = {str(service.get("key")) for service in services if service.get("key")}
    labels = route_labels(desired)
    for rule in p["auth_exceptions"]:
        if rule.get("instance") or rule.get("host") or rule.get("user"):
            matched = any(exception_covers_service(rule, service) for service in services)
        else:
            matched = rule.get("service") in keys or rule.get("service") in labels
        if not matched:
            errors.append(
                "networking.ingress.forward-auth.exceptions entry "
                f"{rule['label']!r} matches no service or route"
            )
    if "sablier" in p["plugins"] and "sablier" not in placed:
        errors.append("networking.ingress.plugins lists sablier but no workload lists sablier")
    seen_host: set[str] = set()
    for service in services:
        if service.get("key") != "sablier":
            continue
        host = str(service.get("host") or "")
        if host in seen_host:
            errors.append(f"host {host} lists sablier more than once")
        seen_host.add(host)
    return errors


def key_only_ready(desired: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    p = policy(desired)
    for h in hosts(desired):
        identity = h.get("identity") or {}
        ssh = str(identity.get("ssh") or p["ssh"])
        if ssh != "key-only":
            continue
        admins = [u for u in (h.get("users") or []) if host_user_is_sysadmin(u)]
        if not any(u.get("ssh-keys") for u in admins):
            errors.append(f"identity.ssh is key-only on {h.get('name')} but no sysadmin has ssh-keys")
    return errors


def ingress_host(desired: dict[str, Any]) -> dict[str, str] | None:
    for s in all_services(desired):
        if s["key"] == "caddy":
            return {"name": s["host"], "ip": s["host_ip"] or ""}
    return None
