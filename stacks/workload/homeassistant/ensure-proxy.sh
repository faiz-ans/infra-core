#!/bin/sh
# Patch persistent configuration.yaml, then start HA if this is the container entrypoint.
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
text = path.read_text(encoding="utf-8", errors="replace")
if re.search(r"(?m)^\s*trusted_proxies\s*:", text):
    sys.exit(0)
block = (
    "  use_x_forwarded_for: true\n"
    "  trusted_proxies:\n"
    "    - 192.168.0.0/16\n"
    "    - 10.0.0.0/8\n"
    "    - 172.16.0.0/12\n"
    "    - 192.168.65.0/24\n"
    "    - 169.254.0.0/16\n"
    "    - 0.0.0.0/0\n"
    "    - ::/0\n"
)
m = re.search(r"(?m)^http:\s*$", text)
if m:
    text = text[: m.end()] + "\n" + block + text[m.end() :]
else:
    text = text.rstrip() + "\n\nhttp:\n" + block
path.write_text(text, encoding="utf-8")
print(f"wrote trusted_proxies in {path}", file=sys.stderr)
PY
if [ -x /init ]; then
  exec /init "$@"
fi
