#!/usr/bin/env bash
# Merge catalog Docker Engine log caps into /etc/docker/daemon.json on Core.
# Run as root (core.sh calls this after Docker is installed). Safe to re-run.
#   sudo bash bootstrap/core-docker-engine.sh
#
# Caps json-file logs so /var/lib/docker cannot fill the OS disk. Does not
# change DATA_ROOT. Restarts docker if the file changed.
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "${here}/.." && pwd)"
# Prefer next to this script (a bootstrap/ tree on Core). linux/ is the repo copy.
fragment="${here}/docker-engine.json"
if [[ ! -f "${fragment}" ]]; then
  fragment="${repo}/linux/docker-engine.json"
fi
if [[ ! -f "${fragment}" ]]; then
  echo "docker-engine.json not found (bootstrap/ or linux/)."
  exit 1
fi

dest=/etc/docker/daemon.json
mkdir -p /etc/docker

set +e
python3 - "${fragment}" "${dest}" <<'PY'
import json, pathlib, sys

frag_path, dest_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
frag = json.loads(frag_path.read_text())
if dest_path.is_file() and dest_path.read_text().strip():
    daemon = json.loads(dest_path.read_text())
else:
    daemon = {}

changed = False
for key in ("log-driver", "log-opts", "ipv6"):
    if key in frag and daemon.get(key) != frag[key]:
        daemon[key] = frag[key]
        changed = True

tmp = dest_path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(daemon, indent=2) + "\n")
tmp.replace(dest_path)
print(f"Wrote {dest_path}")
sys.exit(0 if changed else 2)
PY
rc=$?
set -e

if [[ $rc -eq 2 ]]; then
  echo "daemon.json already had catalog log settings; no restart."
  exit 0
fi
if [[ $rc -ne 0 ]]; then
  exit "$rc"
fi

systemctl restart docker
echo "Restarted docker (log rotation applied)."
