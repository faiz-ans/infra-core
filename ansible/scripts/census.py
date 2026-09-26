#!/usr/bin/env python3
"""Task A: hostname, MAC, OS, timezone, locale, lsblk, GPU, UPS, PWM, uid>1000."""
from __future__ import annotations

import json
import os
import pwd
import socket
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _os() -> dict:
    data = {"name": "", "version": ""}
    path = Path("/etc/os-release")
    if path.is_file():
        kv = {}
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k] = v.strip().strip('"')
        data["name"] = kv.get("ID") or kv.get("NAME") or ""
        data["version"] = kv.get("VERSION_ID") or ""
    return data


def _mac() -> str:
    try:
        route = _run(["ip", "-4", "route", "get", "1.1.1.1"])
        dev = ""
        for i, tok in enumerate(route.split()):
            if tok == "dev" and i + 1 < len(route.split()):
                dev = route.split()[i + 1]
                break
        if dev:
            addr = Path(f"/sys/class/net/{dev}/address")
            if addr.is_file():
                return addr.read_text().strip()
    except OSError:
        pass
    return ""


def _ip() -> str:
    route = _run(["ip", "-4", "route", "get", "1.1.1.1"])
    parts = route.split()
    for i, tok in enumerate(parts):
        if tok == "src" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _lsblk() -> list:
    raw = _run(["lsblk", "-J", "-o", "NAME,KNAME,TYPE,SIZE,FSTYPE,UUID,MOUNTPOINT,MODEL"])
    if not raw:
        return []
    try:
        return json.loads(raw).get("blockdevices") or []
    except json.JSONDecodeError:
        return []


def _gpus() -> list:
    raw = _run(["lspci", "-nn"])
    return [line for line in raw.splitlines() if "VGA" in line or "3D" in line or "Display" in line]


def _ups() -> list:
    raw = _run(["lsusb"])
    keys = ("UPS", "APC", "CyberPower", "Tripp", "nut")
    return [line for line in raw.splitlines() if any(k.lower() in line.lower() for k in keys)]


def _pwm() -> str:
    hwmon = Path("/sys/class/hwmon")
    if not hwmon.is_dir():
        return ""
    for node in sorted(hwmon.iterdir()):
        for pwm in sorted(node.glob("pwm[0-9]")):
            return str(pwm)
    return ""


def _users() -> list:
    out = []
    for ent in pwd.getpwall():
        if ent.pw_uid > 1000 and ent.pw_uid < 65534:
            out.append({"name": ent.pw_name, "uid": ent.pw_uid, "gid": ent.pw_gid})
    return out


def main() -> None:
    print(
        json.dumps(
            {
                "hostname": socket.gethostname(),
                "ip": _ip(),
                "mac": _mac(),
                "os": _os(),
                "timezone": Path("/etc/timezone").read_text().strip()
                if Path("/etc/timezone").is_file()
                else (os.environ.get("TZ") or ""),
                "locale": (os.environ.get("LANG") or _run(["localectl", "status"])),
                "disks": _lsblk(),
                "gpus": _gpus(),
                "ups": _ups(),
                "pwm": _pwm(),
                "users": _users(),
            }
        )
    )


if __name__ == "__main__":
    main()
