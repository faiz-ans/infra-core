"""Write observed.yaml from GET facts. Never overwrite an existing desired file."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SKIP_DISK = re.compile(r"^(loop|zram|ram|sr|mmcblk\d+boot)")
USB_LAN = re.compile(r"\b(lan|ethernet)\b", re.I)
NVIDIA_SMI_L = re.compile(
    r"^GPU\s+(\d+):\s+(.+?)\s+\(UUID:\s*([^)]+)\)\s*$",
    re.I,
)


def usb_is_onboard(item: dict[str, Any] | str) -> bool:
    """Root hubs, hub chips, and USB-ethernet NICs — not plug-in peripherals."""
    if isinstance(item, str):
        ident, name = item.lower(), item.lower()
    else:
        ident = str(item.get("id") or "").lower()
        name = str(item.get("name") or ident).lower()
    if ident.startswith("1d6b:") or "root hub" in name:
        return True
    if "usb hub" in name or re.search(r"\bhub\b", name):
        return True
    if USB_LAN.search(name):
        return True
    return False


def _quoted_str(dumper: yaml.SafeDumper, data: str):
    style = '"' if (":" in data or "," in data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


yaml.add_representer(str, _quoted_str, Dumper=yaml.SafeDumper)


def _json_b64(raw: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw:
        try:
            return json.loads(base64.b64decode(raw))
        except (ValueError, json.JSONDecodeError, TypeError):
            pass
    return fallback if isinstance(fallback, dict) else {}


def merge_observed(host_facts: list[dict[str, Any]]) -> dict[str, Any]:
    hosts_out = []
    services: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    for hf in host_facts:
        census = _json_b64(hf.get("census_b64"), hf.get("census") or {})
        state = _json_b64(hf.get("state_b64"), hf.get("state") or {})
        name = census.get("hostname") or hf.get("name") or ""
        hosts_out.append(
            {
                "name": name,
                "ip": hf.get("ip") or census.get("ip") or "",
                "mac": census.get("mac") or "",
                "os": census.get("os") or {},
                "timezone": census.get("timezone") or "",
                "locale": census.get("locale") or "",
                "disks": census.get("disks") or [],
                "gpus": census.get("gpus") or [],
                "usb": [u for u in (census.get("usb") or []) if not usb_is_onboard(u)],
                "pwm": census.get("pwm") or "",
                "unix_users": census.get("users") or [],
                "ssh_user": hf.get("ssh_user") or "",
                "ssh": census.get("ssh") or "",
                "mounts": state.get("mounts") or [],
                "nfs_exports": state.get("nfs_exports") or "",
                "smb": state.get("smb"),
                "cockpit": state.get("cockpit"),
                "podman": state.get("podman"),
                "containers": state.get("containers") or [],
                "ldap": state.get("ldap") or {},
            }
        )
        for c in state.get("containers") or []:
            if isinstance(c, str):
                services.append({"host": name, "name": c})
            elif isinstance(c, dict):
                services.append({"host": name, "name": c.get("name") or c.get("Names")})
        for u in census.get("users") or []:
            if isinstance(u, dict) and u.get("name"):
                users.append({"name": u["name"], "uid": u.get("uid"), "gid": u.get("gid"), "host": name})
    return {
        "observed": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hosts": hosts_out,
        },
        "services": services,
        "users": users,
    }


def write_observed(path: Path, host_facts: list[dict[str, Any]]) -> Path:
    path.write_text(yaml.safe_dump(merge_observed(host_facts), sort_keys=False), encoding="utf-8")
    return path


DATA_FS = {"ext4", "xfs", "btrfs"}
SKIP_PART_FS = {"vfat", "swap", "iso9660", "squashfs"}


def _disk_name(disk: dict[str, Any]) -> str:
    """lsblk MODEL, or the transport when the model is empty."""
    model = str(disk.get("model") or "").strip()
    if model:
        return model
    return str(disk.get("tran") or "").strip().lower()


def _relevant_parts(disk: dict[str, Any]) -> list[dict[str, Any]]:
    """Data partitions only. Boot, swap, and other non-data filesystems stay off the scaffold."""
    out: list[dict[str, Any]] = []
    for ch in disk.get("children") or []:
        if str(ch.get("type") or "") != "part":
            continue
        fstype = str(ch.get("fstype") or "").lower()
        if fstype in SKIP_PART_FS:
            continue
        mount = str(ch.get("mountpoint") or "")
        if mount == "[SWAP]" or mount.startswith("/boot"):
            continue
        if fstype not in DATA_FS or not str(ch.get("uuid") or "").strip():
            continue
        out.append(ch)
    return out


def _partition_item(disk: dict[str, Any], part: dict[str, Any]) -> dict[str, Any]:
    kname = str(part.get("name") or part.get("kname") or "part")
    model = str(disk.get("model") or "").strip()
    item: dict[str, Any] = {"id": kname, "name": model or kname}
    size = str(part.get("size") or "").strip()
    if size:
        item["size"] = size
    uuid = str(part.get("uuid") or "").strip()
    if uuid:
        item["uuid"] = uuid
    return item


def scaffold_disks(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observed disks only: no loop/zram/boot slices or swap. WSL VHDs are internal.

    A disk with data partitions lists those partitions (they own roots and storage drives).
    A disk with no partitions keeps name, size, and uuid on itself.
    A disk with neither a data-partition UUID nor its own filesystem UUID is omitted.
    """
    out: list[dict[str, Any]] = []
    for d in devices:
        if d.get("type") != "disk":
            continue
        if d.get("fstype") == "swap":
            continue
        kname = str(d.get("name") or d.get("kname") or "")
        if SKIP_DISK.match(kname):
            continue
        tran = str(d.get("tran") or "").lower()
        model = str(d.get("model") or "").lower()
        internal = tran == "mmc" or model == "virtual disk"
        parts = _relevant_parts(d)
        item: dict[str, Any] = {"id": kname or "disk"}
        if parts:
            if internal:
                item["internal"] = True
            item["partitions"] = [_partition_item(d, p) for p in parts]
        else:
            label = _disk_name(d)
            if label:
                item["name"] = label
            size = str(d.get("size") or "").strip()
            if size:
                item["size"] = size
            uuid = str(d.get("uuid") or "").strip()
            if not uuid:
                continue
            item["uuid"] = uuid
            if internal:
                item["internal"] = True
        out.append(item)
    return out


def scaffold_usb(devices: list[Any]) -> list[dict[str, str]]:
    """Plug-in USB peripherals only. No type."""
    out: list[dict[str, str]] = []
    for d in devices:
        if isinstance(d, str):
            ident, name, bus, device = d, d, "", ""
        elif isinstance(d, dict):
            ident = str(d.get("id") or "").strip()
            name = str(d.get("name") or "")
            bus = str(d.get("bus") or "")
            device = str(d.get("device") or "")
        else:
            continue
        if not ident or usb_is_onboard(d if isinstance(d, dict) else {"id": ident, "name": name}):
            continue
        item: dict[str, str] = {"id": ident}
        if bus:
            item["bus"] = bus
        if device:
            item["device"] = device
        if name:
            item["name"] = name
        out.append(item)
    return out


def parse_nvidia_smi_line(line: str) -> dict[str, str] | None:
    """GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-…) → id gpu0, name, uuid."""
    m = NVIDIA_SMI_L.match(str(line or "").strip())
    if not m:
        return None
    return {
        "id": f"gpu{m.group(1)}",
        "name": m.group(2).strip(),
        "uuid": m.group(3).strip(),
    }


def scaffold_gpus(gpus: list[Any]) -> list[dict[str, Any]]:
    """One site.yaml GPU per nvidia-smi -L line. Id is gpu<index> from that output."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for g in gpus:
        if isinstance(g, dict) and g.get("id"):
            parsed = {
                "id": str(g["id"]),
                "name": str(g.get("name") or ""),
                "uuid": str(g.get("uuid") or ""),
            }
        else:
            parsed = parse_nvidia_smi_line(str(g))
        if not parsed or parsed["id"] in seen:
            continue
        seen.add(parsed["id"])
        item: dict[str, Any] = {"id": parsed["id"]}
        if parsed.get("name"):
            item["name"] = parsed["name"]
        if parsed.get("uuid"):
            item["uuid"] = parsed["uuid"]
        item["resource"] = "nvidia.com/gpu"
        out.append(item)
    return out


def _host_users(host: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for u in host.get("unix_users") or []:
        if not isinstance(u, dict) or not u.get("name"):
            continue
        item: dict[str, Any] = {"name": u["name"], "sysadmin": bool(u.get("sysadmin"))}
        keys = [k for k in (u.get("ssh_keys") or []) if k]
        if keys:
            item["ssh-keys"] = keys
        out.append(item)
    return out


def _env_and_host_fields(
    hosts: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, str]]:
    tzs = [str(h.get("timezone") or "") for h in hosts]
    locales = [str(h.get("locale") or "") for h in hosts]
    env: dict[str, str] = {}
    host_fields: list[dict[str, Any]] = [{} for _ in hosts]
    if tzs and tzs[0] and all(t == tzs[0] for t in tzs):
        env["timezone"] = tzs[0]
    else:
        for i, tz in enumerate(tzs):
            if tz:
                host_fields[i].setdefault("env", {})["timezone"] = tz
    if locales and locales[0] and all(loc == locales[0] for loc in locales):
        env["locale"] = locales[0]
    else:
        for i, loc in enumerate(locales):
            if loc:
                host_fields[i].setdefault("env", {})["locale"] = loc
    sshs = [str(h.get("ssh") or "") for h in hosts]
    identity: dict[str, str] = {}
    if sshs and sshs[0] and all(s == sshs[0] for s in sshs):
        identity["ssh"] = sshs[0]
    else:
        for i, ssh in enumerate(sshs):
            if ssh:
                host_fields[i].setdefault("identity", {})["ssh"] = ssh
    return env, host_fields, identity


def scaffold_desired(observed: dict[str, Any]) -> str:
    """Print-only scaffold. Caller must not write this over an existing site.yaml."""
    hosts = (observed.get("observed") or observed).get("hosts") or []
    env, host_fields, identity = _env_and_host_fields(hosts)
    host_entries: list[dict[str, Any]] = []
    for h, fields in zip(hosts, host_fields):
        osinfo = h.get("os") or {}
        entry: dict[str, Any] = {}
        if h.get("name"):
            entry["name"] = h["name"]
        if h.get("ip"):
            entry["ip"] = h["ip"]
        if h.get("mac"):
            entry["mac"] = h["mac"]
        if osinfo.get("name") or osinfo.get("version"):
            entry["os"] = {
                "name": str(osinfo.get("name") or "").lower(),
                "version": str(osinfo.get("version") or ""),
            }
        users = _host_users(h)
        if users:
            entry["users"] = users
        for key in ("roots", "identity", "operations", "env"):
            if fields.get(key):
                entry[key] = fields[key]
        resources: dict[str, Any] = {}
        disks = scaffold_disks(h.get("disks") or [])
        if disks:
            resources["disks"] = disks
        gpus = scaffold_gpus(h.get("gpus") or [])
        if gpus:
            resources["gpu"] = gpus
        if h.get("pwm"):
            resources["pwm"] = {"path": h["pwm"]}
        usb = scaffold_usb(h.get("usb") or [])
        if usb:
            resources["usb"] = usb
        if resources:
            entry["resources"] = resources
        if entry:
            host_entries.append(entry)
    site_body: dict[str, Any] = {}
    if identity:
        site_body["identity"] = identity
    if env:
        site_body["env"] = env
    site_body["hosts"] = host_entries
    header = "# Scaffold from GET A: observed facts only. Copy to site.yaml and add policy. Do not commit.\n"
    return header + yaml.safe_dump({"site": site_body}, sort_keys=False)
