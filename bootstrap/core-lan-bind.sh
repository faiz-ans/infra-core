#!/usr/bin/env bash
# Install the post-DHCP Pi-hole recreate (host :53 bind) plus Caddy/WG/Komodo restart.
# docker restart cannot rebind published ports. Safe to re-run.
#
#   sudo bash bootstrap/core-lan-bind.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ ! -f "${SCRIPT_DIR}/core-lan-bind" || ! -f "${SCRIPT_DIR}/core-lan-bind.service" ]]; then
  echo "core-lan-bind / core-lan-bind.service missing next to this script."
  exit 1
fi

install -m 755 "${SCRIPT_DIR}/core-lan-bind" /usr/local/sbin/core-lan-bind
install -m 644 "${SCRIPT_DIR}/core-lan-bind.service" /etc/systemd/system/core-lan-bind.service
systemctl daemon-reload
systemctl enable core-lan-bind.service
systemctl start core-lan-bind.service
echo "core-lan-bind.service enabled. journalctl -u core-lan-bind -n 20 --no-pager"
journalctl -u core-lan-bind -n 20 --no-pager || true
