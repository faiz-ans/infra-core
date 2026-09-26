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
    getent = _run(["getent", "passwd"])
    ids = []
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
