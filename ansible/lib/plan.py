"""Build the SET plan consumed by playbooks (NFS, dirs, imports, policy)."""
from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

from .directory import ldap_base_dn, people_homes
from .topology import (
    admin_gui,
    all_services,
    host_by_name,
    shared_host_roots,
    host_roots,
    host_volumes,
    hosts,
    policy,
    root_owners,
    roots,
    site_of,
    volume_host_roots,
)

COMPONENTS = Path(__file__).resolve().parents[2] / "components"
SITE_ROOT_VAR = re.compile(r"\$\{site\.data\.roots\.([A-Za-z0-9_-]+)\}")

GENERATED_NAMES = {"Caddyfile", "configuration.yml", "configuration.yaml"}

IMPORT_TYPE_ALIASES = {
    "users-home": "user-home",
    "groups-home": "group-home",
    "user-root": "users-root",
    "group-root": "groups-root",
}

ROOT_IMPORT_TYPES = {
    "appdata-root": "appdata",
    "groups-root": "groups",
    "users-root": "users",
}

HOME_IMPORT_TYPES = {
    "appdata-home": "appdata",
    "group-home": "groups",
    "user-home": "users",
}


def workload_user(desired: dict[str, Any], host_name: str) -> str:
    for h in hosts(desired):
        if h.get("name") == host_name:
            wl = (h.get("operations") or {}).get("workload") or {}
            return str(wl.get("user") or "")
    return ""


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_strings(item))
        return out
    return []


def referenced_site_roots(service: dict[str, Any]) -> set[str]:
    """Site roots named by ${site.data.roots.<name>} in this instance or its component files."""
    found: set[str] = set()
    for text in _strings(service.get("raw")):
        found.update(SITE_ROOT_VAR.findall(text))
    src = COMPONENTS / str(service.get("component") or service.get("key") or "")
    if not src.is_dir():
        return found
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found.update(SITE_ROOT_VAR.findall(text))
    return found


def inferred_nfs(desired: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Export a site root only when this instance names ${site.data.roots.<name>} and another host owns it."""
    owners = root_owners(desired)
    exports: list[dict[str, str]] = []
    mounts: list[dict[str, str]] = []
    seen_ex: set[tuple] = set()
    seen_mnt: set[tuple] = set()
    for s in all_services(desired):
        consumer = s.get("host") or ""
        consumer_ip = s.get("host_ip") or ""
        for root in referenced_site_roots(s):
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


def disk_mount_path(disk: dict[str, Any]) -> str:
    """Systemd Where= for one disk. internal disks are already `/`; others are `/mnt/site/<id>`."""
    if disk.get("internal"):
        return "/"
    ident = str(disk.get("id") or "disk")
    return f"/mnt/site/{ident}"


def mount_unit_name(path: str) -> str:
    rel = path.strip("/")
    if not rel:
        return "root.mount"
    return rel.replace("/", "-") + ".mount"


def _host_disks(host: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((host.get("resources") or {}).get("disks") or []))


def _host_drives(host: dict[str, Any]) -> list[dict[str, Any]]:
    return list((((host.get("operations") or {}).get("storage") or {}).get("drives") or []))


def _disk_by_id(host: dict[str, Any], disk_id: str) -> dict[str, Any]:
    """Resolve a storage-drive or host-root id to its partition, or to the disk when it has none."""
    for vol in host_volumes(host):
        if vol.get("id") == disk_id:
            return vol
    return {"id": disk_id}


def _host_ip(desired: dict[str, Any], name: str) -> str:
    h = host_by_name(desired, name)
    return str((h or {}).get("ip") or "")


def disk_mounts(desired: dict[str, Any]) -> list[dict[str, str]]:
    """One UUID mount per non-internal disk that owns site/local roots or has imports."""
    units: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for h in hosts(desired):
        name = h.get("name") or ""
        drive_ids = {d.get("id") for d in _host_drives(h)}
        for disk in host_volumes(h):
            ident = disk.get("id") or ""
            if disk.get("internal") or not disk.get("uuid"):
                continue
            if ident not in drive_ids and not disk.get("import") and not volume_host_roots(disk):
                continue
            key = (name, ident)
            if key in seen:
                continue
            seen.add(key)
            where = disk_mount_path(disk)
            units.append(
                {
                    "host": name,
                    "id": ident,
                    "uuid": str(disk.get("uuid") or ""),
                    "where": where,
                    "unit": mount_unit_name(where),
                }
            )
    return units


def root_binds(desired: dict[str, Any]) -> list[dict[str, str]]:
    """Sibling dirs on the owning disk, bind-mounted to site.data.roots.* (or mkdir on `/`)."""
    r = roots(desired)
    out: list[dict[str, str]] = []
    for h in hosts(desired):
        name = h.get("name") or ""
        for drive in _host_drives(h):
            disk = _disk_by_id(h, str(drive.get("id") or ""))
            mount = disk_mount_path(disk)
            for root in drive.get("roots") or []:
                if root not in r:
                    continue
                where = r[root]
                if mount == "/":
                    out.append(
                        {
                            "host": name,
                            "root": root,
                            "kind": "dir",
                            "what": where,
                            "where": where,
                            "unit": "",
                            "disk_unit": "",
                        }
                    )
                    continue
                what = f"{mount}/{root}"
                out.append(
                    {
                        "host": name,
                        "root": root,
                        "kind": "bind",
                        "what": what,
                        "where": where,
                        "unit": mount_unit_name(where),
                        "disk_unit": mount_unit_name(mount),
                    }
                )
    out.extend(local_root_binds(desired))
    return out


def local_root_binds(desired: dict[str, Any]) -> list[dict[str, str]]:
    """Host roots on the owning disk (sibling dir named after the local-root key)."""
    out: list[dict[str, str]] = []
    for h in hosts(desired):
        name = h.get("name") or ""
        declared = host_roots(h)
        if not isinstance(declared, dict):
            continue
        shared = shared_host_roots(desired, h)
        for disk in host_volumes(h):
            mount = disk_mount_path(disk)
            for root in volume_host_roots(disk):
                if root in shared:
                    continue
                where = str(declared.get(root) or "")
                if not where:
                    continue
                if mount == "/":
                    out.append(
                        {
                            "host": name,
                            "root": str(root),
                            "kind": "dir",
                            "what": where,
                            "where": where,
                            "unit": "",
                            "disk_unit": "",
                        }
                    )
                    continue
                what = f"{mount}/{root}"
                out.append(
                    {
                        "host": name,
                        "root": str(root),
                        "kind": "bind",
                        "what": what,
                        "where": where,
                        "unit": mount_unit_name(where),
                        "disk_unit": mount_unit_name(mount),
                    }
                )
    return out


def _normalize_import_type(raw: str) -> str:
    typ = str(raw or "").strip()
    return IMPORT_TYPE_ALIASES.get(typ, typ)


def _relocate_name(item: dict[str, Any], from_rel: str) -> str:
    relocate = item.get("as") if item.get("as") not in (None, "") else item.get("to")
    if relocate not in (None, ""):
        return str(relocate).strip("/")
    return posixpath.basename(str(from_rel).rstrip("/")) or ""


def _stamp_slug(disk_id: str, typ: str, from_rel: str) -> str:
    raw = f"{disk_id}_{typ}_{from_rel}"
    return "".join(c if c.isalnum() else "_" for c in raw)


def _same_place(
    source: str,
    dest: str,
    disk_mount: str,
    dest_root: str,
    dest_root_path: str,
    disk_owns_dest: bool,
) -> bool:
    if posixpath.normpath(source) == posixpath.normpath(dest):
        return True
    if not disk_owns_dest or not dest_root or not dest_root_path:
        return False
    if disk_mount == "/":
        return False
    bind_what = f"{disk_mount}/{dest_root}"
    if dest == dest_root_path:
        return source == bind_what
    if dest.startswith(dest_root_path + "/"):
        return source == bind_what + dest[len(dest_root_path) :]
    return False


def import_blocks(desired: dict[str, Any]) -> list[dict[str, Any]]:
    r = roots(desired)
    owners = root_owners(desired)
    blocks: list[dict[str, Any]] = []
    for h in hosts(desired):
        host_name = h.get("name") or ""
        for disk in host_volumes(h):
            items = disk.get("import")
            if not items:
                continue
            if isinstance(items, dict):
                raise ValueError(
                    f"disk {disk.get('id')!r} import must be a list of "
                    "{type, from, as?} items, not a mapping"
                )
            disk_root = disk_mount_path(disk)
            disk_id = str(disk.get("id") or "")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(f"disk {disk_id!r} import items must be mappings")
                typ = _normalize_import_type(str(item.get("type") or ""))
                from_rel = str(item.get("from") or "")
                if not from_rel:
                    raise ValueError(f"disk {disk_id!r} import is missing from:")
                source = posixpath.normpath(posixpath.join(disk_root, from_rel.lstrip("/")))
                if typ in ROOT_IMPORT_TYPES:
                    dest_root = ROOT_IMPORT_TYPES[typ]
                    dest = r[dest_root]
                elif typ in HOME_IMPORT_TYPES:
                    dest_root = HOME_IMPORT_TYPES[typ]
                    dest = posixpath.normpath(posixpath.join(r[dest_root], _relocate_name(item, from_rel)))
                elif typ == "other":
                    relocate = item.get("as") if item.get("as") not in (None, "") else item.get("to")
                    if relocate in (None, ""):
                        raise ValueError(f"disk {disk_id!r} type other requires as: or to:")
                    dest = str(relocate)
                    dest_root = next((k for k, p in r.items() if dest == p or dest.startswith(p + "/")), "")
                else:
                    raise ValueError(
                        f"disk {disk_id!r} unknown import type {typ!r}; "
                        "use appdata|groups|users-root, appdata-home, group-home, user-home, or other"
                    )
                owner = owners.get(dest_root) or {}
                dest_root_path = r.get(dest_root, "")
                disk_owns_dest = bool(
                    dest_root
                    and owner.get("host") == host_name
                    and owner.get("drive") == disk_id
                )
                name = posixpath.basename(dest.rstrip("/"))
                generated = name in GENERATED_NAMES or posixpath.basename(source) in GENERATED_NAMES
                slug = _stamp_slug(disk_id, typ, from_rel)
                stamp_root = dest_root_path or dest
                blocks.append(
                    {
                        "host": host_name,
                        "disk": disk_id,
                        "type": typ,
                        "from": source,
                        "from_rel": from_rel,
                        "to": dest,
                        "generated": generated,
                        "kind": "file" if generated else "tree",
                        "same_place": _same_place(
                            source, dest, disk_root, dest_root, dest_root_path, disk_owns_dest
                        ),
                        "dest_root": dest_root,
                        "dest_owner": owner.get("host") or "",
                        "remote": bool(owner.get("host") and owner.get("host") != host_name),
                        "stamp": f"{stamp_root}/.import-stamps/{slug}.ok",
                    }
                )
    return blocks


def import_nfs(desired: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Temporary NFS of dest roots so a non-owner host can rsync into them."""
    owners = root_owners(desired)
    exports: list[dict[str, str]] = []
    mounts: list[dict[str, str]] = []
    seen_ex: set[tuple] = set()
    seen_mnt: set[tuple] = set()
    for block in import_blocks(desired):
        if not block.get("remote"):
            continue
        dest_root = block.get("dest_root") or ""
        owner = owners.get(dest_root)
        if not owner or not owner.get("host"):
            continue
        consumer = block["host"]
        consumer_ip = _host_ip(desired, consumer)
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


def site_groups(desired: dict[str, Any]) -> list[str]:
    names = {"all"}
    for u in site_of(desired).get("users") or []:
        for g in u.get("groups") or []:
            names.add(g)
    return sorted(names)


def build_plan(desired: dict[str, Any]) -> dict[str, Any]:
    nfs = inferred_nfs(desired)
    imp_nfs = import_nfs(desired)
    p = policy(desired)
    return {
        "policy": p,
        "roots": roots(desired),
        "owners": root_owners(desired),
        "services": all_services(desired),
        "disk_mounts": disk_mounts(desired),
        "root_binds": root_binds(desired),
        "nfs_exports": nfs["exports"],
        "nfs_mounts": nfs["mounts"],
        "import_nfs_exports": imp_nfs["exports"],
        "import_nfs_mounts": imp_nfs["mounts"],
        "service_dirs": service_dirs(desired),
        "imports": import_blocks(desired),
        "users": site_of(desired).get("users") or [],
        "groups": site_groups(desired),
        "hosts": [{**h, "admin-gui": admin_gui(h.get("admin-gui"))} for h in hosts(desired)],
        "domain": str((site_of(desired).get("env") or {}).get("domain") or ""),
        "ldap": p["ldap"],
        "ldap_base": ldap_base_dn(str((site_of(desired).get("env") or {}).get("domain") or ""))
        if p["ldap"] == "openldap"
        else "",
        "ldap_port": 1389,
        "people_homes": people_homes(p["filesystem"], p["web"]),
        "sso_backend": "ldap" if p["ldap"] == "openldap" else "file",
    }
