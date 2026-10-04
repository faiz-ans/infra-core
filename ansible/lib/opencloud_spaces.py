#!/usr/bin/env python3
"""OpenCloud posix spaces: a user home is the personal space, a group home is a Space.

Homes are matched by directory name. A home with no space xattrs is attached.
Grants that name some other account are replaced with the current one.
A home that already has the right space and the right grants is left as it is.
The home root only lists. Each subroot and everything inside it can be edited.
Nothing here walks file contents.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _list_xattr(path: Path) -> list[str]:
    if hasattr(os, "listxattr"):
        return list(os.listxattr(path))
    out = subprocess.check_output(["xattr", str(path)], text=True)
    return [line for line in out.splitlines() if line]


def _get_xattr(path: Path, name: str) -> bytes:
    if hasattr(os, "getxattr"):
        return os.getxattr(path, name)
    try:
        raw = subprocess.check_output(
            ["xattr", "-p", "-x", name, str(path)], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as exc:
        raise OSError(exc.returncode, name) from exc
    return bytes.fromhex("".join(raw.split()))


def _set_xattr(path: Path, name: str, value: bytes) -> None:
    if hasattr(os, "setxattr"):
        os.setxattr(path, name, value)
        return
    subprocess.run(["xattr", "-w", "-x", name, value.hex(), str(path)], check=True)


def _remove_xattr(path: Path, name: str) -> None:
    if hasattr(os, "removexattr"):
        os.removexattr(path, name)
        return
    subprocess.run(["xattr", "-d", name, str(path)], check=True)

# Viewer on the home root. Editor on a subroot and everything inside it.
# The editor set is what a new folder inherits on the first listing.
LIST_ROLE = "txruq"
EDIT_ROLE = "txrwaduUq"
_UUID = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def oc_uuid(blob: bytes, username: str) -> str | None:
    """openCloudUUID on the user entry.

    The same DN is also stored on group memberships. Those records carry the
    group's id, so the uuid has to come from the user entry itself.
    """
    needle = f"uid={username},ou=users".encode()
    start = 0
    while True:
        at = blob.find(needle, start)
        if at < 0:
            return None
        window = blob[at : at + 1200]
        group = window.find(b"cn=")
        entry = window[:group] if group > 0 else window
        marker = entry.find(b"openCloudUUID")
        if marker >= 0:
            match = _UUID.search(entry[marker:])
            if match:
                return match.group(0).decode()
        start = at + len(needle)


def read_xattrs(path: Path) -> dict[str, bytes]:
    if not path.is_dir():
        return {}
    return {name: _get_xattr(path, name) for name in _list_xattr(path) if name.startswith("user.oc.")}


def _set_xattrs(path: Path, attrs: dict[str, bytes], drop: set[str] | None = None) -> None:
    current = set(_list_xattr(path))
    for name in drop or ():
        if name in current:
            _remove_xattr(path, name)
    for name, value in attrs.items():
        _set_xattr(path, name, value)


def is_space_root(attrs: dict[str, bytes]) -> bool:
    if attrs.get("user.oc.space.type"):
        return True
    sid = attrs.get("user.oc.space.id")
    return bool(sid) and sid == attrs.get("user.oc.id")


def _space_aligned(attrs: dict[str, bytes], kind: str, name: str) -> bool:
    sid = attrs.get("user.oc.id")
    return (
        attrs.get("user.oc.space.type") == kind.encode()
        and attrs.get("user.oc.space.alias") == f"{kind}/{name}".encode()
        and bool(sid)
        and attrs.get("user.oc.space.id") == sid
    )


def _owner_is_space(attrs: dict[str, bytes]) -> bool:
    sid = attrs.get("user.oc.id")
    return (
        bool(sid)
        and attrs.get("user.oc.owner.id") == sid
        and attrs.get("user.oc.owner.type") == b"spaceowner"
        and attrs.get("user.oc.owner.idp", b"") == b""
    )


def personal_current(attrs: dict[str, bytes], username: str, owner: str) -> bool:
    """The home is this user's personal space, and the user is not its owner.

    Owner permissions would make the home root writable. The user is granted
    on the space instead. ``owner`` is accepted so older callers keep working.
    """
    del owner
    return _space_aligned(attrs, "personal", username) and _owner_is_space(attrs)


def project_current(attrs: dict[str, bytes], group: str, member_ids: list[str]) -> bool:
    """Identity only. Member grants are checked when they are written."""
    del member_ids
    return _space_aligned(attrs, "project", group) and _owner_is_space(attrs)


def _stamp() -> bytes:
    now = datetime.now(timezone.utc)
    return (now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond:06d}000Z").encode()


def personal_xattrs(username: str, display: str, space_id: str) -> dict[str, bytes]:
    stamp = _stamp()
    sid = space_id.encode()
    return {
        "user.oc.id": sid,
        "user.oc.space.id": sid,
        "user.oc.name": username.encode(),
        "user.oc.space.name": display.encode(),
        "user.oc.space.type": b"personal",
        "user.oc.space.alias": f"personal/{username}".encode(),
        "user.oc.owner.id": sid,
        "user.oc.owner.idp": b"",
        "user.oc.owner.type": b"spaceowner",
        "user.oc.type": b"2",
        "user.oc.propagation": b"1",
        "user.oc.dirty": b"false",
        "user.oc.mtime": stamp,
        "user.oc.tmtime": stamp,
    }


def project_xattrs(group: str, space_id: str) -> dict[str, bytes]:
    stamp = _stamp()
    return {
        "user.oc.id": space_id.encode(),
        "user.oc.space.id": space_id.encode(),
        "user.oc.name": group.encode(),
        "user.oc.space.name": group.encode(),
        "user.oc.space.type": b"project",
        "user.oc.space.alias": f"project/{group}".encode(),
        "user.oc.owner.id": space_id.encode(),
        "user.oc.owner.idp": b"",
        "user.oc.owner.type": b"spaceowner",
        "user.oc.type": b"2",
        "user.oc.propagation": b"1",
        "user.oc.dirty": b"false",
        "user.oc.mtime": stamp,
        "user.oc.tmtime": stamp,
    }


def demoted_xattrs(attrs: dict[str, bytes], parent_id: str) -> tuple[dict[str, bytes], set[str]]:
    """A former space root becomes a folder inside the personal space."""
    drop = {
        name
        for name in attrs
        if name.startswith("user.oc.space.") or name.startswith("user.oc.owner.") or name.startswith("user.oc.grant.") or name == "user.oc.quota"
    }
    kept = {name: value for name, value in attrs.items() if name not in drop}
    kept["user.oc.parentid"] = parent_id.encode()
    return kept, drop


def _space_id(attrs: dict[str, bytes]) -> str:
    current = attrs.get("user.oc.id")
    if current and attrs.get("user.oc.space.type"):
        return current.decode()
    return str(uuid.uuid4())


def link_user(home: Path, username: str, display: str) -> list[str]:
    """Return container paths that need a posixfs scan. Empty when the space is already this home."""
    if not home.is_dir():
        return []
    attrs = read_xattrs(home)
    scans: list[str] = []
    if personal_current(attrs, username, ""):
        space_id = attrs["user.oc.id"].decode()
    elif _space_aligned(attrs, "personal", username):
        space_id = attrs["user.oc.id"].decode()
        _fix_space_owner(home, space_id)
    else:
        space_id = _space_id(attrs)
        _set_xattrs(home, personal_xattrs(username, display, space_id))
        scans.append(f"/posix/users/{username}")
    for child in _child_dirs(home):
        child_attrs = read_xattrs(child)
        if not child_attrs or not is_space_root(child_attrs):
            continue
        kept, drop = demoted_xattrs(child_attrs, space_id)
        _set_xattrs(child, kept, drop)
        path = f"/posix/users/{username}"
        if path not in scans:
            scans.append(path)
    return scans


def link_group(home: Path, group: str) -> list[str]:
    if not home.is_dir():
        return []
    attrs = read_xattrs(home)
    if project_current(attrs, group, []):
        return []
    if _space_aligned(attrs, "project", group):
        _fix_space_owner(home, attrs["user.oc.id"].decode())
        return []
    _set_xattrs(home, project_xattrs(group, _space_id(attrs)))
    return [f"/posix/groups/{group}"]


def _fix_space_owner(path: Path, space_id: str) -> None:
    sid = space_id.encode()
    _set_xattr(path, "user.oc.owner.id", sid)
    _set_xattr(path, "user.oc.owner.type", b"spaceowner")
    _set_xattr(path, "user.oc.owner.idp", b"")


def _text(path: Path, name: str) -> str:
    try:
        return _get_xattr(path, name).decode().strip("\x00").strip()
    except OSError:
        return ""


def _child_dirs(path: Path) -> list[Path]:
    found = []
    try:
        entries = list(path.iterdir())
    except OSError:
        return found
    for entry in entries:
        if entry.name.startswith(".oc-"):
            continue
        if entry.is_symlink() or not entry.is_dir():
            continue
        found.append(entry)
    return found


def _grant_bytes(principal: str, perms: str) -> bytes:
    flags = "g" if principal.startswith("g:") else ""
    return f"\x00t=A:f={flags}:p={perms}:c=:e=0\n".encode()


def _wanted_grant_names(people: list[str]) -> set[str]:
    return {f"user.oc.grant.{person}" for person in people}


def _put_grant(path: Path, principal: str, perms: str) -> bool:
    key = f"user.oc.grant.{principal}"
    value = _grant_bytes(principal, perms)
    try:
        current = _get_xattr(path, key)
    except OSError:
        current = None
    if current == value:
        return False
    _set_xattr(path, key, value)
    return True


def _drop_other_grants(path: Path, wanted: set[str]) -> bool:
    changed = False
    for name in _list_xattr(path):
        if not (name.startswith("user.oc.grant.u:") or name.startswith("user.oc.grant.g:")):
            continue
        if name in wanted:
            continue
        _remove_xattr(path, name)
        changed = True
    return changed


def _grant_node(path: Path, people: list[str], perms: str, wanted: set[str]) -> bool:
    changed = _drop_other_grants(path, wanted)
    for person in people:
        changed = _put_grant(path, person, perms) or changed
    return changed


def _grant_inside(sub: Path, people: list[str], wanted: set[str]) -> bool:
    """Editor grants on directories inside a subroot, and on files placed directly in it."""
    changed = False
    skip_dir = {".Trash", ".space"}
    for dirpath, dirnames, filenames in os.walk(sub, followlinks=False):
        dirnames[:] = [name for name in dirnames if not name.startswith(".oc-") and name not in skip_dir]
        targets: list[Path] = []
        current = Path(dirpath)
        if current != sub:
            targets.append(current)
        else:
            for name in filenames:
                if name.startswith(".oc-") or name.endswith(".mlock"):
                    continue
                path = current / name
                if not path.is_symlink():
                    targets.append(path)
        for path in targets:
            changed = _grant_node(path, people, EDIT_ROLE, wanted) or changed
    return changed


def _reparent(home: Path, space_id: str) -> bool:
    """Point a folder at the subroot that contains it when it still names the home."""
    changed = False
    for sub in _child_dirs(home):
        sub_id = _text(sub, "user.oc.id")
        if not sub_id or sub_id == space_id:
            continue
        for child in _child_dirs(sub):
            if _text(child, "user.oc.parentid") == space_id:
                _set_xattr(child, "user.oc.parentid", sub_id.encode())
                changed = True
    return changed


def apply_member_grants(home: Path, people: list[str]) -> bool:
    if not people or not home.is_dir():
        return False
    wanted = _wanted_grant_names(people)
    changed = _grant_node(home, people, LIST_ROLE, wanted)
    for child in _child_dirs(home):
        changed = _grant_node(child, people, EDIT_ROLE, wanted) or changed
        changed = _grant_inside(child, people, wanted) or changed
    space_id = _text(home, "user.oc.id")
    if space_id:
        changed = _reparent(home, space_id) or changed
    return changed


def member_names(group: str, users: list[dict[str, Any]]) -> list[str]:
    """Every site user is in all, plus any group they list."""
    names = []
    for user in users:
        groups = ["all"]
        for listed in user.get("groups") or []:
            text = str(listed)
            if text and text not in groups:
                groups.append(text)
        name = str(user.get("name") or "")
        if name and group in groups:
            names.append(name)
    return names


def _pack_str(text: str) -> bytes:
    raw = text.encode()
    n = len(raw)
    if n < 32:
        return bytes([0xA0 | n]) + raw
    if n < 256:
        return bytes([0xD9, n]) + raw
    if n < 65536:
        return b"\xda" + n.to_bytes(2, "big") + raw
    return b"\xdb" + n.to_bytes(4, "big") + raw


def _pack_map(items: dict[str, str]) -> bytes:
    n = len(items)
    if n < 16:
        head = bytes([0x80 | n])
    elif n < 65536:
        head = b"\xde" + n.to_bytes(2, "big")
    else:
        head = b"\xdf" + n.to_bytes(4, "big")
    return head + b"".join(_pack_str(key) + _pack_str(value) for key, value in items.items())


def _unpack_str(blob: bytes, at: int) -> tuple[str, int]:
    kind = blob[at]
    if kind & 0xE0 == 0xA0:
        n = kind & 0x1F
        start = at + 1
    elif kind == 0xD9 or kind == 0xC4:
        n = blob[at + 1]
        start = at + 2
    elif kind == 0xDA or kind == 0xC5:
        n = int.from_bytes(blob[at + 1 : at + 3], "big")
        start = at + 3
    elif kind == 0xDB or kind == 0xC6:
        n = int.from_bytes(blob[at + 1 : at + 5], "big")
        start = at + 5
    else:
        raise ValueError(f"space index value is not a string ({kind:#x})")
    return blob[start : start + n].decode(), start + n


def _unpack_map(blob: bytes) -> dict[str, str]:
    if not blob:
        return {}
    kind = blob[0]
    if kind & 0xF0 == 0x80:
        n = kind & 0x0F
        at = 1
    elif kind == 0xDE:
        n = int.from_bytes(blob[1:3], "big")
        at = 3
    elif kind == 0xDF:
        n = int.from_bytes(blob[1:5], "big")
        at = 5
    else:
        raise ValueError(f"space index is not a map ({kind:#x})")
    items: dict[str, str] = {}
    for _ in range(n):
        key, at = _unpack_str(blob, at)
        value, at = _unpack_str(blob, at)
        items[key] = value
    return items


def _load_index(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return _unpack_map(path.read_bytes())


def _store_index(path: Path, items: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_pack_map(items))
    os.chmod(path, 0o600)
    os.chmod(path.parent, 0o700)
    prototype = path.parent.parent
    if prototype.exists():
        st = prototype.stat()
        os.chown(path, st.st_uid, st.st_gid)
        os.chown(path.parent, st.st_uid, st.st_gid)


def _ensure_index(path: Path, entries: dict[str, str]) -> bool:
    current = _load_index(path)
    merged = dict(current)
    merged.update(entries)
    if merged == current:
        return False
    _store_index(path, merged)
    return True


def publish_indexes(
    indexes: Path,
    personal: dict[str, str],
    projects: dict[str, list[str]],
) -> set[str]:
    """Write by-user-id and by-type indexes. Return space ids that were missing."""
    missing: set[str] = set()
    personal_entries = {space_id: space_id for space_id in personal.values()}
    project_entries: dict[str, str] = {}
    owners = set(personal) | set(projects)
    for owner in owners:
        entries: dict[str, str] = {}
        space_id = personal.get(owner)
        if space_id:
            entries[space_id] = space_id
        for project_id in projects.get(owner) or []:
            entries[project_id] = project_id
            project_entries[project_id] = project_id
        before = _load_index(indexes / "by-user-id" / f"{owner}.mpk")
        if _ensure_index(indexes / "by-user-id" / f"{owner}.mpk", entries):
            missing.update(space for space in entries if before.get(space) != space)
    if personal_entries:
        _ensure_index(indexes / "by-type" / "personal.mpk", personal_entries)
    if project_entries:
        _ensure_index(indexes / "by-type" / "project.mpk", project_entries)
    return missing


def apply_spaces(spec: dict[str, Any]) -> list[str]:
    """Attach homes to current accounts. Return container paths to scan."""
    scans, _changed = align_spaces(spec)
    return scans


def align_spaces(spec: dict[str, Any]) -> tuple[list[str], bool]:
    """Attach homes and write grants. The bool is true when a grant or owner changed."""
    users_root = Path(spec["users_root"])
    groups_root = Path(spec["groups_root"])
    blob = Path(spec["idm"]).read_bytes() if spec.get("idm") and Path(spec["idm"]).is_file() else b""
    users = list(spec.get("users") or [])
    scans: list[str] = []
    changed = False
    owners: dict[str, str] = {}
    for user in users:
        name = str(user.get("name") or "")
        if not name:
            continue
        owner = oc_uuid(blob, name)
        if not owner:
            continue
        owners[name] = owner
        display = str(user.get("displayname") or name)
        scans.extend(link_user(users_root / name, name, display))
        if apply_member_grants(users_root / name, [f"u:{owner}"]):
            changed = True
            print(f"updated {users_root / name}")
    group_ids: dict[str, str] = {}
    for group in spec.get("groups") or []:
        name = str(group)
        member_ids = [owners[member] for member in member_names(name, users) if member in owners]
        home = groups_root / name
        scans.extend(link_group(home, name))
        if member_ids and apply_member_grants(home, [f"u:{member}" for member in member_ids]):
            changed = True
            print(f"updated {home}")
        attrs = read_xattrs(home)
        space_id = attrs.get("user.oc.id")
        if space_id and attrs.get("user.oc.space.type") == b"project":
            group_ids[name] = space_id.decode()
    personal: dict[str, str] = {}
    projects: dict[str, list[str]] = {}
    paths: dict[str, str] = {}
    for name, owner in owners.items():
        attrs = read_xattrs(users_root / name)
        space_id = attrs.get("user.oc.id")
        if space_id and attrs.get("user.oc.space.type") == b"personal":
            text = space_id.decode()
            personal[owner] = text
            paths[text] = f"/posix/users/{name}"
        projects[owner] = []
        for group, gid in group_ids.items():
            members = [owners[member] for member in member_names(group, users) if member in owners]
            if owner in members:
                projects[owner].append(gid)
                paths[gid] = f"/posix/groups/{group}"
    index_root = str(spec.get("indexes") or "")
    if index_root:
        for space_id in publish_indexes(Path(index_root), personal, projects):
            path = paths.get(space_id)
            if path and path not in scans:
                scans.append(path)
    return scans, changed


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    for path in apply_spaces(spec):
        print(f"scan {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
