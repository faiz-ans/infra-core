"""Backup sources: read grants for the engine's user, NFS when the tree is elsewhere."""
from __future__ import annotations

import posixpath
from typing import Any

from .topology import all_services, host_by_name, host_roots, hosts, root_owners, roots, site_of


def backup_spec(desired: dict[str, Any]) -> dict[str, Any]:
    data = site_of(desired).get("data") or {}
    spec = data.get("backup") if isinstance(data, dict) else None
    return spec if isinstance(spec, dict) else {}


def backup_runner(desired: dict[str, Any]) -> dict[str, Any] | None:
    """The placed service named by data.backup.engine."""
    engine = str(backup_spec(desired).get("engine") or "").strip()
    if not engine or engine == "none":
        return None
    found = [service for service in all_services(desired) if service.get("key") == engine]
    if len(found) != 1:
        return None
    return found[0]


def _clean_rel(path: str) -> str | None:
    """'' for the whole home. None when the path escapes the home."""
    raw = str(path or "/").strip() or "/"
    if not raw.startswith("/"):
        return None
    norm = posixpath.normpath(raw)
    if norm != "/" and (norm.startswith("../") or norm == ".."):
        return None
    if norm == "/":
        return ""
    return norm


def backup_sources(desired: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    """Resolved sources. client_path is what the backup host bind-mounts."""
    spec = backup_spec(desired)
    sources_node = spec.get("sources") if isinstance(spec.get("sources"), dict) else {}
    runner = backup_runner(desired)
    runner_host = str((runner or {}).get("host") or "")
    out: list[dict[str, str]] = []
    errors: list[str] = []
    owners = root_owners(desired)
    declared = roots(desired)

    def add(owner_host: str, owner_ip: str, path: str, container: str) -> None:
        remote = bool(runner_host) and owner_host != runner_host
        if remote:
            client = "/mnt/backup" + container
        else:
            client = path
        out.append(
            {
                "owner_host": owner_host,
                "owner_ip": owner_ip,
                "path": path,
                "container": container,
                "client_path": client,
                "remote": "yes" if remote else "",
            }
        )

    for item in sources_node.get("roots") or []:
        if isinstance(item, str):
            owner = owners.get(item)
            if owner is None or item not in declared:
                errors.append(f"data.backup.sources.roots names unknown site root {item}")
                continue
            add(owner["host"], owner["host_ip"], owner["path"], f"/data/{item}")
            continue
        if isinstance(item, dict) and len(item) == 1:
            host_name, root_name = next(iter(item.items()))
            host = host_by_name(desired, str(host_name))
            root_name = str(root_name)
            if host is None:
                errors.append(f"data.backup.sources.roots names unknown host {host_name}")
                continue
            local = host_roots(host)
            if root_name not in local:
                errors.append(f"data.backup.sources.roots names unknown host root {host_name}:{root_name}")
                continue
            add(
                str(host.get("name") or ""),
                str(host.get("ip") or ""),
                local[root_name],
                f"/data/hosts/{host_name}/{root_name}",
            )
            continue
        errors.append("data.backup.sources.roots entry must be a site root or one host: root pair")

    for item in sources_node.get("homes") or []:
        if not isinstance(item, dict) or len(item) != 1:
            errors.append("data.backup.sources.homes entry must be one of user, group, or app")
            continue
        kind, body = next(iter(item.items()))
        if kind not in ("user", "group", "app") or not isinstance(body, dict):
            errors.append("data.backup.sources.homes entry must be one of user, group, or app")
            continue
        name = str(body.get("name") or "")
        rel = _clean_rel(str(body.get("path") or "/"))
        if not name or rel is None:
            errors.append(f"data.backup.sources.homes {kind} needs a name and a path under /")
            continue
        if kind == "user":
            root_name, container = "users", f"/data/homes/users/{name}{rel}"
            known = {str(user.get("name") or "") for user in site_of(desired).get("users") or []}
            if name not in known:
                errors.append(f"data.backup.sources.homes user {name} is not a site user")
                continue
        elif kind == "group":
            root_name, container = "groups", f"/data/homes/groups/{name}{rel}"
        else:
            root_name, container = "appdata", f"/data/homes/apps/{name}{rel}"
        owner = owners.get(root_name)
        if owner is None:
            errors.append(f"data.backup.sources.homes {kind} {name} needs the {root_name} site root")
            continue
        add(owner["host"], owner["host_ip"], posixpath.join(owner["path"], name) + rel, container)
    if (sources_node.get("roots") or sources_node.get("homes")) and runner is None:
        engine = str(spec.get("engine") or "").strip() or "unset"
        count = len([service for service in all_services(desired) if service.get("key") == engine])
        if count == 0:
            errors.append(f"data.backup.engine is {engine} but no workload lists it")
        elif count > 1:
            errors.append(f"data.backup.engine is {engine} but more than one workload lists it")
    return out, errors


def backup_grants(desired: dict[str, Any]) -> list[dict[str, str]]:
    """Read ACLs on the backup host. A remote source is reached by NFS, not a local account."""
    runner = backup_runner(desired)
    if runner is None:
        return []
    user = str(runner.get("user") or "")
    host = str(runner.get("host") or "")
    grants = []
    for source in backup_sources(desired)[0]:
        if source["remote"] or source["owner_host"] != host:
            continue
        grants.append({"host": host, "user": user, "path": source["path"]})
    return grants


def backup_nfs(desired: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Export a source that does not live on the backup host, and mount it there."""
    runner = backup_runner(desired)
    if runner is None:
        return {"exports": [], "mounts": []}
    client = str(runner.get("host_ip") or "")
    consumer = str(runner.get("host") or "")
    exports: list[dict[str, str]] = []
    mounts: list[dict[str, str]] = []
    seen_ex: set[tuple[str, str, str]] = set()
    seen_mnt: set[tuple[str, str]] = set()
    for source in backup_sources(desired)[0]:
        if not source["remote"]:
            continue
        ex_key = (source["owner_host"], source["path"], client)
        if ex_key not in seen_ex:
            seen_ex.add(ex_key)
            exports.append(
                {
                    "host": source["owner_host"],
                    "path": source["path"],
                    "client_ip": client,
                    "workload_user": str(runner.get("user") or ""),
                }
            )
        mnt_key = (consumer, source["client_path"])
        if mnt_key not in seen_mnt:
            seen_mnt.add(mnt_key)
            mounts.append(
                {
                    "host": consumer,
                    "path": source["client_path"],
                    "server_ip": source["owner_ip"],
                    "export": source["path"],
                }
            )
    return {"exports": exports, "mounts": mounts}


def validate_backup(desired: dict[str, Any]) -> list[str]:
    _sources, errors = backup_sources(desired)
    return errors
