#!/usr/bin/env bash
# Install or enable host REDIRECT for :53/:80/:443.
#
#   sudo bash bootstrap/core/core-lan-bind.sh --install-only   # Layer 0 (disabled)
#   sudo bash bootstrap/core/core-lan-bind.sh --enable         # after :15353 :8080 :8443
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODE="${1:---install-only}"

if [[ ! -f "${SCRIPT_DIR}/core-lan-bind" || ! -f "${SCRIPT_DIR}/core-lan-bind.service" ]]; then
  echo "core-lan-bind / core-lan-bind.service missing next to this script."
  exit 1
fi

install_units() {
  install -m 755 "${SCRIPT_DIR}/core-lan-bind" /usr/local/sbin/core-lan-bind
  install -m 644 "${SCRIPT_DIR}/core-lan-bind.service" /etc/systemd/system/core-lan-bind.service
  if [[ -f "${SCRIPT_DIR}/core-lan-bind.timer" ]]; then
    install -m 644 "${SCRIPT_DIR}/core-lan-bind.timer" /etc/systemd/system/core-lan-bind.timer
  fi
  rm -f /etc/systemd/system/docker.service
  rm -rf /etc/systemd/system/docker.service.d
  systemctl daemon-reload
  systemctl disable --now core-lan-bind.timer 2>/dev/null || true
  systemctl disable --now core-lan-bind.service 2>/dev/null || true
  echo "Installed core-lan-bind (disabled). Enable after Pi-hole :15353 and Caddy :8080/:8443 listen."
}

port_up() {
  local port=$1 proto=${2:-tcp}
  if [[ "${proto}" == udp ]]; then
    ss -uln 2>/dev/null | grep -qE ":${port}[[:space:]]"
  else
    ss -tln 2>/dev/null | grep -qE ":${port}[[:space:]]"
  fi
}

enable_bind() {
  local missing=0
  port_up 15353 udp || { echo "need UDP :15353 (Pi-hole)"; missing=1; }
  port_up 8080 tcp || { echo "need TCP :8080 (Caddy)"; missing=1; }
  port_up 8443 tcp || { echo "need TCP :8443 (Caddy)"; missing=1; }
  if [[ "${missing}" -ne 0 ]]; then
    echo "Refuse to enable lan-bind until those ports listen (apply core-bootstrap first)."
    exit 1
  fi
  systemctl enable --now core-lan-bind.service
  if [[ -f /etc/systemd/system/core-lan-bind.timer ]]; then
    systemctl enable --now core-lan-bind.timer
  fi
  systemctl restart core-lan-bind.service
  CORE_DNS_MODE=pihole bash "${SCRIPT_DIR}/core-net.sh"
  echo "getent hosts github.com (must succeed):"
  getent hosts github.com || echo "warn: public DNS still failing"
  echo "journalctl -u core-lan-bind -n 25 --no-pager"
  journalctl -u core-lan-bind -n 25 --no-pager || true
}

case "${MODE}" in
  --install-only|"")
    install_units
    ;;
  --enable)
    install_units
    enable_bind
    ;;
  *)
    echo "Usage: sudo bash bootstrap/core/core-lan-bind.sh --install-only|--enable"
    exit 1
    ;;
esac
