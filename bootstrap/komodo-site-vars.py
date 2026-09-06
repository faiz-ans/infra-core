#!/usr/bin/env python3
"""List Komodo [secrets] keys required by topology.toml + stack fragments.

Usage:
  python3 bootstrap/komodo-site-vars.py [--topology PATH] [--fragments DIR]

Prints lines: KEY<TAB>MODE[<TAB>EXTRA]
  MODE: prompt | secret | generate | default | empty | fixed
  EXTRA: default value (default/fixed) or prompt label (prompt/secret)

Always-required platform (OMV/Docker/Komodo/Caddy/OpenCloud) is included even if
topology omits a stack name.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPOLOGY = ROOT / "stacks" / "komodo" / "topology.toml"
DEFAULT_FRAGMENTS = ROOT / "stacks" / "komodo" / "fragments"

# Always on every site (user requirement).
ALWAYS_STACKS = ("caddy", "opencloud", "authelia", "pihole")

# Keys not referenced as [[VAR]] in fragments but required for bootstrap.
ALWAYS_KEYS: dict[str, tuple[str, str]] = {
    "CATALOG_REPO": ("prompt", "Catalog owner/repo path (Gitea; same name as GitHub mirror)"),
    "CORE_SERVER": ("default", "core"),
    "KOMODO_ADMIN_USER": ("default", "admin"),
    "KOMODO_ADMIN_PASSWORD": ("secret", "Komodo admin password"),
    "AUTHELIA_FAIZ_PASSWORD": ("secret", "Authelia password for user 'faiz'"),
    "AUTHELIA_DIANA_PASSWORD": ("secret", "Authelia password for user 'diana'"),
    "NFS_EXPORT": ("fixed", "/shared"),
    "NFS_USERS": ("fixed", "/users"),
}

# How to obtain fragment [[VAR]] keys (override). Unlisted secrets → generate.
KEY_MODE: dict[str, tuple[str, str]] = {
    "DOMAIN": ("prompt", "Domain"),
    "TZ": ("default", "America/Los_Angeles"),
    "PUID": ("default", "1000"),
    "PGID": ("default", "1000"),
    "NAS_LAN_IP": ("prompt", "LAN IP of this host (Core)"),
    "HTPC_UPSTREAM": ("prompt", "LAN IP of the remote Periphery host (published Docker ports)"),
    "DATA_ROOT": ("prompt", "DATA_ROOT path"),
    "PERIPHERY_SERVER": ("default", "periphery"),
    "WG_HOST": ("prompt", "WireGuard public endpoint host (off-LAN DNS name)"),
    "SIGNUPS_ALLOWED": ("default", "true"),
    "LINKDING_SUPERUSER_NAME": ("default", "admin"),
    "BYTESTASH_ALLOW_NEW_ACCOUNTS": ("default", "true"),
    "RESTIC_REST_USER": ("default", "restic"),
    "BACKUP_DRIVE": ("prompt", "HTPC BACKUP_DRIVE path (Restic REST data)"),
    "WEATHER_LATITUDE": ("empty", ""),
    "WEATHER_LONGITUDE": ("empty", ""),
    "PIHOLE_WEBPASSWORD": ("empty", ""),
    "PIHOLE_PERIPHERY_WEBPASSWORD": ("empty", ""),
    "HOMEPAGE_VAR_PIHOLE_TOKEN": ("empty", ""),
    "HOMEPAGE_VAR_JELLYFIN_KEY": ("empty", ""),
    "HOMEPAGE_VAR_SONARR_KEY": ("empty", ""),
    "HOMEPAGE_VAR_RADARR_KEY": ("empty", ""),
    "HOMEPAGE_VAR_PROWLARR_KEY": ("empty", ""),
    "HOMEPAGE_VAR_QBIT_USERNAME": ("empty", ""),
    "HOMEPAGE_VAR_QBIT_PASSWORD": ("empty", ""),
    "HOMEPAGE_VAR_GRAFANA_KEY": ("empty", ""),
    "HOMEPAGE_VAR_WGEASY_PASSWORD": ("empty", ""),
    "VAULTWARDEN_ADMIN_TOKEN": ("generate", ""),
    "OPENCLOUD_ADMIN_PASSWORD": ("generate", ""),
    "IMMICH_DB_PASSWORD": ("generate", ""),
    "LINKDING_SUPERUSER_PASSWORD": ("generate", ""),
    "ADVENTURELOG_POSTGRES_PASSWORD": ("generate", ""),
    "ADVENTURELOG_ADMIN_PASSWORD": ("generate", ""),
    "TRANSMUTE_AUTH_SECRET_KEY": ("generate", ""),
    "BYTESTASH_JWT_SECRET": ("generate", ""),
    "OPENREADER_AUTH_SECRET": ("generate", ""),
    "N8N_ENCRYPTION_KEY": ("generate", ""),
    "RESTIC_PASSWORD": ("generate", ""),
    "RESTIC_REST_PASSWORD": ("generate", ""),
    "GRAFANA_ADMIN_PASSWORD": ("generate", ""),
    "WG_UI_PASSWORD": ("generate", ""),
    "AUTHELIA_JWT_SECRET": ("generate", ""),
    "AUTHELIA_SESSION_SECRET": ("generate", ""),
    "AUTHELIA_STORAGE_ENCRYPTION_KEY": ("generate", ""),
    "AUTHELIA_OIDC_HMAC_SECRET": ("generate", ""),
    "OIDC_CLIENT_SECRET": ("generate", ""),
}


def parse_topology(text: str) -> dict:
    servers: list[str] = []
    stacks: dict[str, dict] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r'^servers\s*=\s*\[(.*)\]\s*$', line)
        if m:
            servers = re.findall(r'"([^"]+)"', m.group(1))
            continue
        m = re.match(r'^\[stacks\.([^\]]+)\]\s*$', line)
        if m:
            current = m.group(1)
            stacks[current] = {}
            continue
        if current is None:
            continue
        m = re.match(r'^(\w+)\s*=\s*"([^"]*)"\s*$', line)
        if m:
            stacks[current][m.group(1)] = m.group(2)
            continue
        m = re.match(r'^(\w+)\s*=\s*(true|false)\s*$', line)
        if m:
            stacks[current][m.group(1)] = m.group(2) == "true"
    return {"servers": servers, "stacks": stacks}


def fragment_vars(path: Path) -> set[str]:
    return set(re.findall(r"\[\[([A-Z0-9_]+)\]\]", path.read_text()))


def fragment_deploy_enabled(path: Path) -> bool:
    """Honor deploy = false in the stack fragment (ResourceSync cold start)."""
    m = re.search(r"^deploy\s*=\s*(true|false)\s*$", path.read_text(), re.M)
    if m and m.group(1) == "false":
        return False
    return True


def mode_for(key: str) -> tuple[str, str]:
    if key in KEY_MODE:
        return KEY_MODE[key]
    if key.endswith("_PASSWORD") or key.endswith("_SECRET") or key.endswith("_TOKEN") or key.endswith("_KEY"):
        return ("generate", "")
    return ("prompt", key)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topology", type=Path, default=DEFAULT_TOPOLOGY)
    ap.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENTS)
    args = ap.parse_args()

    if not args.topology.is_file():
        sys.exit(f"missing topology: {args.topology}")
    topo = parse_topology(args.topology.read_text())
    enabled = {
        name
        for name, meta in topo["stacks"].items()
        if meta.get("enabled", True) is not False
    }
    enabled.update(ALWAYS_STACKS)

    needed: set[str] = set(ALWAYS_KEYS)
    has_remote = False
    for name in sorted(enabled):
        frag = args.fragments / f"{name}.toml"
        if not frag.is_file():
            continue
        # Still note remote servers for HTPC_UPSTREAM even if deploy=false.
        meta = topo["stacks"].get(name, {})
        if meta.get("server") and meta["server"] != "core":
            has_remote = True
        if not fragment_deploy_enabled(frag) and name not in ALWAYS_STACKS:
            continue
        needed |= fragment_vars(frag)

    if has_remote:
        needed.add("PERIPHERY_SERVER")
        needed.add("HTPC_UPSTREAM")
    elif "caddy" in enabled:
        needed.add("HTPC_UPSTREAM")

    seen: set[str] = set()
    for key, (mode, extra) in ALWAYS_KEYS.items():
        if key in needed:
            print(f"{key}\t{mode}\t{extra}")
            seen.add(key)
    for key in sorted(needed - seen):
        mode, extra = mode_for(key)
        if key == "DATA_ROOT":
            mode, extra = "fixed", "${DATA_ROOT}"
        if key == "DOMAIN" and mode == "prompt":
            mode, extra = "default", "home.lan"
        print(f"{key}\t{mode}\t{extra}")


if __name__ == "__main__":
    main()
