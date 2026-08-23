#!/usr/bin/env bash
# Patch HA configuration.yaml on the NAS DATA_ROOT (same tree the HTPC NFS-mounts).
# Caddy always sends X-Forwarded-For; HA returns 400 until trusted_proxies is in this file.
#   sudo bash bootstrap/ha-trusted-proxies.sh
# Then recreate/restart the homeassistant container on the HTPC.
set -euo pipefail
DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
cfg="${DATA_ROOT}/system/periphery/homeassistant/configuration.yaml"
here="$(cd "$(dirname "$0")" && pwd)"
script="${here}/../stacks/workload/homeassistant/ensure-proxy.sh"
if [[ ! -f "${script}" ]]; then
  echo "Run from an infra-core checkout (missing ${script})."
  exit 1
fi
HA_CONFIG="$cfg" sh "${script}"
echo "Restart homeassistant on the HTPC (Komodo Redeploy or docker restart homeassistant)."
echo "Then: curl -skI https://ha.home.lan"
