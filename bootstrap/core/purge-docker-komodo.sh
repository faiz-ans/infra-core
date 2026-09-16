#!/usr/bin/env bash
# Export Docker named volumes that are not already under DATA_ROOT, then remove
# docker-ce, Komodo, and leftover bridges. Safe-ish to re-run.
#
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-... bash bootstrap/core/purge-docker-komodo.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-}"
if [[ -z "${DATA_ROOT}" && -f /etc/komodo/bootstrap-state.env ]]; then
  # shellcheck disable=SC1091
  source /etc/komodo/bootstrap-state.env
fi
if [[ -z "${DATA_ROOT}" ]]; then
  echo "Set DATA_ROOT."
  exit 1
fi

EXPORT="${DATA_ROOT}/system/docker-volume-export"
mkdir -p "${EXPORT}"

if command -v docker >/dev/null 2>&1; then
  echo "Listing Docker volumes (copy anything not already on DATA_ROOT):"
  docker volume ls -q || true
  echo "Especially export Caddy /data if it is a named volume:"
  echo "  docker run --rm -v caddy_caddy-data:/from:ro -v ${EXPORT}:/to alpine tar -C /from -cf /to/caddy-data.tar ."
  echo "Copy that tarball onto ${DATA_ROOT}/system/caddy/data before applying the Caddy component."
  docker ps -a --format '{{.Names}} {{.Status}}' || true
  systemctl stop docker.socket docker.service 2>/dev/null || true
fi

export DEBIAN_FRONTEND=noninteractive
apt-get remove -y --purge docker-ce docker-ce-cli docker-ce-rootless-extras docker-compose-plugin containerd.io 2>/dev/null || true
apt-get autoremove -y || true
rm -rf /var/lib/docker /var/lib/containerd /etc/docker /etc/komodo
ip link delete docker0 2>/dev/null || true
ip link delete edge 2>/dev/null || true
# OMV Compose plugin (if present)
if command -v omv-rpc >/dev/null 2>&1; then
  echo "Disable OMV Compose plugin in the workbench if it is installed."
fi
echo "Purge step finished. dockerd should be gone."
command -v dockerd >/dev/null 2>&1 && echo "WARN: dockerd binary still present" || echo "dockerd absent"
