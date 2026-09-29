#!/usr/bin/env python3
"""Task A: hostname, MAC, OS, timezone, locale, lsblk, GPU, USB, PWM, uid>=1000."""
from __future__ import annotations

import glob
import grp
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path


def _run(cmd: list[str]) -> str:
    """Keep stdout even when the command exits non-zero (lsusb can do that mid-replug)."""
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return (proc.stdout or "").strip()
    except FileNotFoundError:
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
        toks = route.split()
        dev = ""
        for i, tok in enumerate(toks):
            if tok == "dev" and i + 1 < len(toks):
                dev = toks[i + 1]
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
    raw = _run(
        ["lsblk", "-J", "-o", "NAME,KNAME,TYPE,SIZE,FSTYPE,UUID,MOUNTPOINT,MODEL,TRAN"]
    )
    if not raw:
        return []
    try:
        return json.loads(raw).get("blockdevices") or []
    except json.JSONDecodeError:
        return []


NVIDIA_SMI_L = re.compile(
    r"^GPU\s+(\d+):\s+(.+?)\s+\(UUID:\s*([^)]+)\)\s*$",
    re.I,
)


def is_site_host_path(path: str) -> bool:
    """Stay on this host’s filesystem. Never walk /mnt (another OS’s disks)."""
    return "/mnt/" not in str(path).replace("\\", "/")


def parse_nvidia_smi_line(line: str) -> dict | None:
    """GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-…) → id gpu0, name, uuid."""
    m = NVIDIA_SMI_L.match(str(line or "").strip())
    if not m:
        return None
    return {
        "id": f"gpu{m.group(1)}",
        "name": m.group(2).strip(),
        "uuid": m.group(3).strip(),
    }


def nvidia_device_listed(gpus: list) -> bool:
    """True only for an NVIDIA device string. Not Microsoft Basic Render."""
    for g in gpus:
        s = str(g).lower()
        if "basic render" in s:
            continue
        stripped = s.replace("nvidia-smi", "")
        if "nvidia" in stripped or "geforce" in s or re.search(r"\brtx\b", s):
            return True
    return False


def nvidia_smi_bins() -> list[Path]:
    """nvidia-smi on this host, including vendor lib dirs not on PATH."""
    found: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if not is_site_host_path(str(p)):
            return
        if not p.is_file():
            return
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key in seen:
            return
        seen.add(key)
        found.append(p)

    which = shutil.which("nvidia-smi")
    if which:
        add(Path(which))
    for p in (Path("/usr/bin/nvidia-smi"), Path("/usr/local/bin/nvidia-smi"), Path("/usr/local/cuda/bin/nvidia-smi")):
        add(p)
    for pat in ("/usr/lib/*/nvidia-smi", "/usr/lib/*/*/nvidia-smi"):
        for hit in glob.glob(pat):
            add(Path(hit))
    return found


def _nvidia_smi_lines() -> list[str]:
    lines: list[str] = []
    for binary in nvidia_smi_bins():
        lib = str(binary.parent)
        env = os.environ.copy()
        env["PATH"] = lib + ":" + env.get("PATH", "")
        old_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = lib + ((":" + old_ld) if old_ld else "")
        try:
            raw = subprocess.check_output(
                [str(binary), "-L"],
                text=True,
                stderr=subprocess.DEVNULL,
                env=env,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError):
            continue
        for line in raw.splitlines():
            if line.strip():
                lines.append(line.strip())
        if lines:
            break
    return lines


def _gpus() -> list:
    """nvidia-smi -L listings on this host. Id is gpu<index> from that output."""
    out: list[dict] = []
    seen: set[str] = set()
    for line in _nvidia_smi_lines():
        item = parse_nvidia_smi_line(line)
        if not item or item["id"] in seen:
            continue
        seen.add(item["id"])
        out.append(item)
    return out


LSUSB_ID = re.compile(r"ID\s+([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})", re.I)
LSUSB_BUS = re.compile(r"Bus\s+(\d+)\s+Device\s+(\d+)", re.I)
USB_LAN = re.compile(r"\b(lan|ethernet)\b", re.I)


def usb_is_onboard(item: dict) -> bool:
    """Root hubs, hub chips, and USB-ethernet NICs — not plug-in peripherals."""
    ident = str(item.get("id") or "").lower()
    name = str(item.get("name") or "").lower()
    if ident.startswith("1d6b:") or "root hub" in name:
        return True
    if "usb hub" in name or re.search(r"\bhub\b", name):
        return True
    if USB_LAN.search(name):
        return True
    return False


def parse_lsusb_line(line: str) -> dict | None:
    """Parse one lsusb line. Never classify device type."""
    raw = str(line or "").strip().strip("\x00")
    if not raw:
        return None
    item: dict[str, str] = {}
    id_m = LSUSB_ID.search(raw)
    if id_m:
        item["id"] = f"{id_m.group(1).lower().zfill(4)}:{id_m.group(2).lower().zfill(4)}"
        name = raw[id_m.end() :].strip()
        if name:
            item["name"] = name
    bus_m = LSUSB_BUS.search(raw)
    if bus_m:
        item["bus"] = bus_m.group(1)
        item["device"] = bus_m.group(2)
    if "id" not in item and "bus" not in item:
        return None
    if "id" not in item:
        item["id"] = raw
    return item


def parse_sysfs_usb(
    vendor: str,
    product: str,
    manufacturer: str = "",
    product_name: str = "",
    bus: str = "",
    device: str = "",
) -> dict | None:
    """One /sys/bus/usb/devices node with idVendor/idProduct."""
    vendor = str(vendor or "").strip().lower()
    product = str(product or "").strip().lower()
    if not vendor or not product:
        return None
    item: dict[str, str] = {"id": f"{vendor.zfill(4)}:{product.zfill(4)}"}
    if str(bus or "").strip():
        item["bus"] = str(bus).strip().zfill(3)
    if str(device or "").strip():
        item["device"] = str(device).strip().zfill(3)
    name = " ".join(
        part for part in (str(manufacturer or "").strip(), str(product_name or "").strip()) if part
    )
    if name:
        item["name"] = name
    return item


def merge_usb(devices: list) -> list:
    """Dedupe by vendor:product. Keep the richer name (lsusb over short sysfs)."""
    out: dict[str, dict] = {}
    for item in devices:
        if not item or usb_is_onboard(item):
            continue
        key = str(item.get("id") or "")
        if not key:
            continue
        prev = out.get(key)
        if prev is None or len(item.get("name") or "") > len(prev.get("name") or ""):
            out[key] = item
    return list(out.values())


def _read_sysfs(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _usb_sysfs() -> list:
    root = Path("/sys/bus/usb/devices")
    if not root.is_dir():
        return []
    out = []
    for node in sorted(root.iterdir()):
        vendor = _read_sysfs(node / "idVendor")
        product = _read_sysfs(node / "idProduct")
        item = parse_sysfs_usb(
            vendor,
            product,
            _read_sysfs(node / "manufacturer"),
            _read_sysfs(node / "product"),
            _read_sysfs(node / "busnum"),
            _read_sysfs(node / "devnum"),
        )
        if item:
            out.append(item)
    return out


def _usb_lsusb() -> list:
    raw = (
        _run(["/usr/bin/env", "LC_ALL=C", "/usr/bin/lsusb"])
        or _run(["/usr/bin/lsusb"])
        or _run(["env", "LC_ALL=C", "lsusb"])
        or _run(["lsusb"])
    )
    out = []
    for line in raw.splitlines():
        item = parse_lsusb_line(line)
        if item:
            out.append(item)
    return out


def _usb() -> list:
    """sysfs first (still there while lsusb misses a replug), then lsusb names."""
    found = merge_usb(_usb_sysfs() + _usb_lsusb())
    if found:
        return found
    time.sleep(0.4)
    return merge_usb(_usb_sysfs() + _usb_lsusb())


def _pwm() -> str:
    hwmon = Path("/sys/class/hwmon")
    if not hwmon.is_dir():
        return ""
    for node in sorted(hwmon.iterdir()):
        for pwm in sorted(node.glob("pwm[0-9]")):
            return str(pwm)
    return ""


ADMIN_GROUPS = {"sudo", "admin", "wheel"}


def user_is_sysadmin(groups: list[str], sudo_listing: str = "") -> bool:
    """True when the user is in an admin group or sudo -l shows they may run commands."""
    if ADMIN_GROUPS.intersection(str(g) for g in groups):
        return True
    text = str(sudo_listing or "").lower()
    return "may run the following commands" in text


def _group_names(username: str, gid: int) -> list[str]:
    names: list[str] = []
    try:
        primary = grp.getgrgid(gid)
        names.append(primary.gr_name)
    except KeyError:
        pass
    for ent in grp.getgrall():
        if username in ent.gr_mem and ent.gr_name not in names:
            names.append(ent.gr_name)
    return names


def _sudo_listing(username: str) -> str:
    return _run(["sudo", "-n", "-l", "-U", username])


def _ssh_keys(home: str) -> list[str]:
    path = Path(home) / ".ssh" / "authorized_keys"
    if not path.is_file():
        return []
    keys = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.append(line)
    return keys


def _users() -> list:
    out = []
    for ent in pwd.getpwall():
        if ent.pw_uid < 1000 or ent.pw_uid >= 65534:
            continue
        groups = _group_names(ent.pw_name, ent.pw_gid)
        out.append(
            {
                "name": ent.pw_name,
                "uid": ent.pw_uid,
                "gid": ent.pw_gid,
                "sysadmin": user_is_sysadmin(groups, "" if ADMIN_GROUPS.intersection(groups) else _sudo_listing(ent.pw_name)),
                "ssh_keys": _ssh_keys(ent.pw_dir),
            }
        )
    return out


def _timezone() -> str:
    tz = Path("/etc/timezone")
    if tz.is_file():
        return tz.read_text().strip()
    return _run(["timedatectl", "show", "-p", "Timezone", "--value"])


def ssh_policy_from_settings(passwordauthentication: str, pubkeyauthentication: str = "yes") -> str:
    """Map effective sshd settings to site.identity.ssh: true | false | key-only."""
    pwd = (passwordauthentication or "").lower()
    pub = (pubkeyauthentication or "yes").lower()
    if pwd == "no" and pub != "no":
        return "key-only"
    if pwd == "yes":
        return "true"
    return ""


def _sshd_t_value(key: str) -> str:
    raw = _run(["sshd", "-T"])
    if not raw:
        return ""
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == key.lower():
            return parts[1].lower()
    return ""


def _sshd_file_value(key: str) -> str:
    last = ""
    paths = [Path("/etc/ssh/sshd_config")]
    drop = Path("/etc/ssh/sshd_config.d")
    if drop.is_dir():
        paths.extend(sorted(drop.glob("*.conf")))
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) >= 2 and parts[0].lower() == key.lower():
                last = parts[1].lower()
    return last


def _ssh_policy() -> str:
    pwd = _sshd_t_value("passwordauthentication") or _sshd_file_value("PasswordAuthentication")
    pub = _sshd_t_value("pubkeyauthentication") or _sshd_file_value("PubkeyAuthentication") or "yes"
    return ssh_policy_from_settings(pwd, pub)


def _locale() -> str:
    for path in (Path("/etc/default/locale"), Path("/etc/locale.conf")):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if line.startswith("LANG="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("LANG") or ""


def main() -> None:
    print(
        json.dumps(
            {
                "hostname": socket.gethostname(),
                "ip": _ip(),
                "mac": _mac(),
                "os": _os(),
                "timezone": _timezone(),
                "locale": _locale(),
                "disks": _lsblk(),
                "gpus": _gpus(),
                "usb": _usb(),
                "pwm": _pwm(),
                "users": _users(),
                "ssh": _ssh_policy(),
            }
        )
    )


if __name__ == "__main__":
    main()
