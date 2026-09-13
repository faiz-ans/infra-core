#!/usr/bin/env bash
# Compatibility wrapper: prep then layout.
# Greenfield: run data-root-prep.sh before OpenCloud; data-root-layout.sh after publish.
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root/data-root-perms.sh
#
# Existing site that only needs new system/<app> dirs: run data-root-prep.sh.
# Layout walks shared/ (chmod/ACL). That can stall HTPC NFS mounts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/data-root-prep.sh"
bash "${SCRIPT_DIR}/data-root-layout.sh"
