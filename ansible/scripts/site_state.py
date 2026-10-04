#!/usr/bin/env python3
"""Task B: findmnt, exports, Cockpit/Podman, containers, LDAP join."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _present(unit_or_bin: str) -> bool:
    if shutil.which(unit_or_bin):
        return True
    return _run(["systemctl", "is-active", unit_or_bin]) in ("active", "activating")


def _parse_ldap(text: str) -> list[dict]:
    ids: list[dict] = []
    cur: dict = {}
    for line in text.splitlines():
        if line.startswith("dn:"):
            if cur.get("name"):
                ids.append(cur)
            cur = {}
            continue
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key == "uid":
            cur["name"] = value
        elif key == "uidNumber" and value.isdigit():
            cur["uid"] = int(value)
        elif key == "entryUUID":
            cur["id"] = value
    if cur.get("name"):
        ids.append(cur)
    return ids


def _directory_ids() -> list[dict]:
    """LDAP entryUUID for each posix account. Anonymous search cannot read them."""
    homes = sorted(Path("/home").glob("*/.config/containers/systemd/openldap/openldap.container"))
    rootful = Path("/etc/containers/systemd/openldap/openldap.container")
    if rootful.is_file():
        prefix: list[str] = ["podman", "exec", "openldap", "sh", "-c"]
    elif homes:
        user = homes[0].parts[2]
        uid = _run(["id", "-u", user])
        if not uid:
            return []
        prefix = [
            "runuser",
            "-u",
            user,
            "--",
            "env",
            f"XDG_RUNTIME_DIR=/run/user/{uid}",
            "podman",
            "exec",
            "openldap",
            "sh",
            "-c",
        ]
    else:
        return []
    script = (
        'base=$(ldapsearch -x -LLL -s base -b "" namingContexts | awk \'/^namingContexts:/{print $2; exit}\')\n'
        'test -n "$base" || exit 1\n'
        'ldapsearch -x -LLL -H ldap://127.0.0.1 -D "cn=admin,${base}" -w "$LDAP_ADMIN_PASSWORD" '
        '-b "$base" "(objectClass=posixAccount)" uid entryUUID uidNumber\n'
    )
    return _parse_ldap(_run(prefix + [script]))


def main() -> None:
    exports = ""
    for p in (Path("/etc/exports"), Path("/etc/exports.d")):
        if p.is_file():
            exports += p.read_text()
        elif p.is_dir():
            for f in sorted(p.glob("*.exports")):
                exports += f.read_text()
    ldap = {"joined": False, "ids": []}
    sssd = Path("/etc/sssd/sssd.conf")
    if sssd.is_file():
        ldap["joined"] = "ldap" in sssd.read_text()
    ids = _directory_ids()
    if not ids:
        getent = _run(["getent", "passwd"])
        for line in getent.splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                try:
                    uid = int(parts[2])
                except ValueError:
                    continue
                if uid >= 10000:
                    ids.append({"name": parts[0], "uid": uid, "gid": int(parts[3]) if parts[3].isdigit() else None})
    ldap["ids"] = ids
    containers = []
    for user_flag in ([], ["--user"]):
        raw = _run(["podman", *user_flag, "ps", "--format", "{{.Names}}"])
        for name in raw.splitlines():
            if name and name not in containers:
                containers.append(name)
    print(
        json.dumps(
            {
                "mounts": [ln for ln in _run(["findmnt", "-J", "-o", "TARGET,SOURCE,FSTYPE,UUID"]).splitlines()],
                "nfs_exports": exports,
                "smb": Path("/etc/samba/smb.conf").is_file() or _present("smbd"),
                "cockpit": _present("cockpit") or Path("/usr/lib/cockpit").is_dir(),
                "podman": bool(shutil.which("podman")),
                "containers": containers,
                "ldap": ldap,
            }
        )
    )


if __name__ == "__main__":
    main()
