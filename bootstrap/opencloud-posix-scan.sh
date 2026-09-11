#!/usr/bin/env bash
# Install the PosixFS assimilate timer. Safe to re-run. core.sh calls this.
#
#   sudo bash bootstrap/opencloud-posix-scan.sh
#
# Then: systemctl start opencloud-posix-scan.service  # catch up now
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ ! -f "${SCRIPT_DIR}/opencloud-posix-scan" || ! -f "${SCRIPT_DIR}/opencloud-posix-scan.service" ]]; then
  echo "opencloud-posix-scan / .service missing next to this script."
  exit 1
fi

install -m 755 "${SCRIPT_DIR}/opencloud-posix-scan" /usr/local/sbin/opencloud-posix-scan
install -m 644 "${SCRIPT_DIR}/opencloud-posix-scan.service" /etc/systemd/system/opencloud-posix-scan.service
install -m 644 "${SCRIPT_DIR}/opencloud-posix-scan.timer" /etc/systemd/system/opencloud-posix-scan.timer

systemctl daemon-reload
systemctl enable opencloud-posix-scan.timer
systemctl start opencloud-posix-scan.timer
systemctl is-enabled opencloud-posix-scan.timer
echo "Catch-up now: sudo systemctl start opencloud-posix-scan.service"
echo "journalctl -u opencloud-posix-scan -n 25 --no-pager"
