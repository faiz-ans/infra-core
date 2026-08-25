#!/usr/bin/env python3
"""Write Caddy trusted_proxies into the HA config volume before /init.

Docker Desktop file binds of configuration.yaml are dropped or hide the
volume copy, so a git bind of that file is not enough to prevent 400s.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BEGIN = "# infra-core-http-begin"
END = "# infra-core-http-end"
CONFIG = Path("/config/configuration.yaml")
HTTP_YAML = Path("/ensure-http/http.yaml")


def load_http_block() -> str:
    text = HTTP_YAML.read_text(encoding="utf-8").strip() + "\n"
    return f"{BEGIN}\n{text}{END}\n"


def replace_marked(text: str, chunk: str) -> str:
    pattern = re.compile(rf"{re.escape(BEGIN)}.*?{re.escape(END)}\n?", re.S)
    return pattern.sub(chunk, text)


def inject_into_http(text: str) -> str:
    if "trusted_proxies" in text and "use_x_forwarded_for" in text:
        return text
    lines = ["  use_x_forwarded_for: true\n"]
    if "trusted_proxies" not in text:
        lines.append("  trusted_proxies:\n    - 0.0.0.0/0\n    - ::/0\n")
    inject = "".join(lines)
    if "use_x_forwarded_for" in text:
        inject = "  trusted_proxies:\n    - 0.0.0.0/0\n    - ::/0\n"
    return re.sub(r"(^http:\n)", r"\1" + inject, text, count=1, flags=re.M)


def ensure(text: str, chunk: str) -> str:
    if BEGIN in text:
        return replace_marked(text, chunk)
    if re.search(r"^http:", text, re.M):
        return inject_into_http(text)
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
