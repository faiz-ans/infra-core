#!/usr/bin/env python3
"""Write Caddy trusted_proxies into the HA config volume before /init.

Replaces any existing http: block so a leftover !include or commented copy
cannot leave use_x_forwarded_for unset (HA 400s on X-Forwarded-For).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BEGIN = "# infra-core-http-begin"
END = "# infra-core-http-end"
CONFIG = Path("/config/configuration.yaml")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
