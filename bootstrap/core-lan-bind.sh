#!/usr/bin/env bash
# Install LAN :53 REDIRECT (127.0.0.1:15353) and a docker.service that does
# not wait on network-online. Safe to re-run. core.sh calls this.
#
#   sudo bash bootstrap/core-lan-bind.sh
#
# Re-run after a docker-ce upgrade so /etc/systemd/system/docker.service
# is rebuilt from the new vendor unit.
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

if ! grep -q DNS_PROXY_PORT "${SCRIPT_DIR}/core-lan-bind"; then
  echo "This core-lan-bind is too old (no 15353 REDIRECT)."
  exit 1
fi

install -m 755 "${SCRIPT_DIR}/core-lan-bind" /usr/local/sbin/core-lan-bind
install -m 644 "${SCRIPT_DIR}/core-lan-bind.service" /etc/systemd/system/core-lan-bind.service
if [[ -f "${SCRIPT_DIR}/core-lan-bind.timer" ]]; then
  install -m 644 "${SCRIPT_DIR}/core-lan-bind.timer" /etc/systemd/system/core-lan-bind.timer
fi

# Drop-ins can only ADD After=/Wants=; they cannot remove network-online.
# Shadow the vendor unit. Re-run this installer after a docker-ce upgrade.
vendor=/usr/lib/systemd/system/docker.service
if [[ -f "${vendor}" ]]; then
  awk '
    /^After=/ {
      print "After=docker.socket firewalld.service containerd.service local-fs.target"
      next
    }
    /^Wants=/ {
      print "Wants=containerd.service"
      next
    }
    { print }
  ' "${vendor}" > /etc/systemd/system/docker.service
  rm -f /etc/systemd/system/docker.service.d/no-network-online.conf
  rmdir /etc/systemd/system/docker.service.d 2>/dev/null || true
fi

systemctl daemon-reload
systemctl show docker -p After -p Wants --no-pager || true
systemctl enable docker.socket docker.service 2>/dev/null || true
systemctl start docker.service 2>/dev/null || true
systemctl enable core-lan-bind.service core-lan-bind.timer 2>/dev/null || true
systemctl restart core-lan-bind.service
systemctl start core-lan-bind.timer 2>/dev/null || true
systemctl is-enabled docker.service core-lan-bind.service core-lan-bind.timer
echo "journalctl -u core-lan-bind -n 25 --no-pager"
journalctl -u core-lan-bind -n 25 --no-pager || true
