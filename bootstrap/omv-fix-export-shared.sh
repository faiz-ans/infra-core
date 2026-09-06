#!/usr/bin/env bash
# Compatibility wrapper: full NFS harden lives in omv-nfs.sh now.
#   sudo HTPC_IP=192.168.1.111 bash bootstrap/omv-fix-export-shared.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
HTPC_IP="${HTPC_IP:-192.168.1.111}"
export HTPC_IP DATA_ROOT="${DATA_ROOT:-}"
exec bash "${here}/omv-nfs.sh"
