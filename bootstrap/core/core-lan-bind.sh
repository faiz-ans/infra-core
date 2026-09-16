#!/usr/bin/env bash
# Install host REDIRECT for :53/:80/:443. Safe to re-run. core.sh calls this.
#
#   sudo bash bootstrap/core/core-lan-bind.sh
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
if [[ -f "${SCRIPT_DIR}/core-lan-bind.timer" ]]; then
  install -m 644 "${SCRIPT_DIR}/core-lan-bind.timer" /etc/systemd/system/core-lan-bind.timer
fi

# Stop shadowing docker.service if a previous bootstrap left it.
rm -f /etc/systemd/system/docker.service
rm -rf /etc/systemd/system/docker.service.d

systemctl daemon-reload
systemctl enable core-lan-bind.service 2>/dev/null || true
if [[ -f /etc/systemd/system/core-lan-bind.timer ]]; then
  systemctl enable --now core-lan-bind.timer
fi
systemctl restart core-lan-bind.service || true
echo "journalctl -u core-lan-bind -n 25 --no-pager"
journalctl -u core-lan-bind -n 25 --no-pager || true
