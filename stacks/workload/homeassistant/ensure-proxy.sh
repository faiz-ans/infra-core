#!/bin/sh
# Replace every top-level http: block with one reverse-proxy block.
# Duplicate http: keys make HA keep the first (often empty) and ignore trusted_proxies.
# HA_CONFIG overrides the path (Core can patch the NFS file without /init).
set -e
cfg="${HA_CONFIG:-/config/configuration.yaml}"
mkdir -p "$(dirname "$cfg")"
if [ ! -f "$cfg" ]; then
  printf '%s\n' 'default_config:' > "$cfg"
fi
python3 - "$cfg" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
http_block = (
    "http:\n"
    "  use_x_forwarded_for: true\n"
    "  trusted_proxies:\n"
    "    - 192.168.0.0/16\n"
    "    - 10.0.0.0/8\n"
    "    - 172.16.0.0/12\n"
    "    - 172.24.0.0/16\n"
    "    - 192.168.65.0/24\n"
    "    - 169.254.0.0/16\n"
    "    - 0.0.0.0/0\n"
    "    - ::/0\n"
)

def strip_http(src: str) -> str:
    lines = src.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        if re.match(r"^http:\s*(#.*)?$", lines[i]):
            i += 1
            while i < len(lines):
                raw = lines[i]
                if raw.strip() == "":
                    i += 1
                    continue
                if raw[0] in " \t":
                    i += 1
                    continue
                break
            continue
        out.append(lines[i])
        i += 1
    return "".join(out).rstrip() + "\n"

new = strip_http(text) + "\n" + http_block
if new != text:
    path.write_text(new, encoding="utf-8")
    print(f"rewrote single http: block in {path}", file=sys.stderr)
PY
if [ -x /init ]; then
  exec /init "$@"
fi
