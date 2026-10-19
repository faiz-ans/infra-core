#!/usr/bin/env python3
"""Write Caddy trusted_proxies into the HA config volume before /init.

Home Assistant migrates http: YAML into .storage/http once, then ignores the
YAML. A new proxy list is only a five-minute trial. If nobody promotes it,
HA restarts on the previous config and answers 400 to X-Forwarded-For.
The store's stable slot is written here so the next boot uses it immediately.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BEGIN = "# infra-core-http-begin"
END = "# infra-core-http-end"
CONFIG = Path("/config/configuration.yaml")
STORE = Path("/config/.storage/http")
HTTP_YAML = Path("/ensure-http/http.yaml")
HTTP_RE = re.compile(
    r"^http:.*?(?=^[a-zA-Z0-9_][a-zA-Z0-9_]*:|\Z)",
    re.M | re.S,
)
MARKED_RE = re.compile(rf"{re.escape(BEGIN)}.*?{re.escape(END)}\n?", re.S)


def load_http_block() -> str:
    text = HTTP_YAML.read_text(encoding="utf-8")
    nas = (os.environ.get("NAS_LAN_IP") or "").strip()
    if nas:
        text = text.replace("__NAS_LAN_IP__", nas)
    else:
        text = "\n".join(line for line in text.splitlines() if "__NAS_LAN_IP__" not in line) + "\n"
    return f"{BEGIN}\n{text.strip()}\n{END}\n"


def proxy_networks(block: str) -> list[str]:
    nets: list[str] = []
    in_list = False
    for line in block.splitlines():
        if line.startswith("  trusted_proxies:"):
            in_list = True
            continue
        if not in_list:
            continue
        if line.startswith("    - "):
            nets.append(str(ipaddress.ip_network(line.split("-", 1)[1].strip())))
        else:
            break
    return nets


def write_store(proxies: list[str]) -> None:
    """Stable config HA will run. Pending stays empty so the trial cannot revert it."""
    now = datetime.now(timezone.utc).isoformat()
    stable = {
        "server_port": 8123,
        "use_x_forwarded_for": True,
        "trusted_proxies": proxies,
        "cors_allowed_origins": ["https://cast.home-assistant.io"],
        "login_attempts_threshold": -1,
        "ip_ban_enabled": True,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
        "created_at": now,
        "error": None,
        "error_message": None,
    }
    doc = {
        "version": 2,
        "minor_version": 2,
        "key": "http",
        "data": {"stable": stable, "pending": None, "yaml_migration_done": True},
    }
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def ensure(text: str, chunk: str) -> str:
    text = MARKED_RE.sub("", text)
    text = HTTP_RE.sub("", text, count=1)
    stripped = text.lstrip()
    return chunk + ("\n" + stripped if stripped else "")


def main() -> int:
    chunk = load_http_block()
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.is_dir():
        print("ensure-http: /config/configuration.yaml is a directory (bad bind); not patching", file=sys.stderr)
        return 1
    existing = CONFIG.read_text(encoding="utf-8") if CONFIG.exists() else "default_config:\n"
    CONFIG.write_text(ensure(existing, chunk), encoding="utf-8")
    write_store(proxy_networks(chunk))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
