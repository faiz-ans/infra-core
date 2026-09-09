#!/usr/bin/env bash
# X1509 12V PWM cage fan: enable the CM5 cooling_fan overlay and a host
# service that sets duty from max(CPU, HDD). Safe to re-run.
#
#   sudo bash bootstrap/core-fan.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
need_reboot=0

if [[ ! -f "${SCRIPT_DIR}/core-fan-control" || ! -f "${SCRIPT_DIR}/core-fan.service" ]]; then
  echo "core-fan-control / core-fan.service missing next to core-fan.sh."
  exit 1
fi

# apt-get install -y smartmontools
export DEBIAN_FRONTEND=noninteractive
apt-get install -y smartmontools >/dev/null

# modprobe drivetemp
# echo drivetemp > /etc/modules-load.d/core-fan.conf
modprobe drivetemp 2>/dev/null || true
echo drivetemp > /etc/modules-load.d/core-fan.conf

cfg=""
if [[ -f /boot/firmware/config.txt ]]; then
  cfg=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
  cfg=/boot/config.txt
fi

if [[ -n "${cfg}" ]] && ! grep -qE '^[[:space:]]*dtparam=cooling_fan=on' "${cfg}"; then
  printf '\n# infra-core X1509 cage fan (12-pin PWM header)\ndtparam=cooling_fan=on\n' >> "${cfg}"
  echo "Wrote dtparam=cooling_fan=on to ${cfg}."
  need_reboot=1
fi

if ! [[ -e /sys/devices/platform/cooling_fan/hwmon/hwmon*/pwm1 ]]; then
  # dtoverlay cooling_fan
  if command -v dtoverlay >/dev/null 2>&1; then
    dtoverlay cooling_fan 2>/dev/null || true
  fi
fi

# install -m 755 bootstrap/core-fan-control /usr/local/sbin/core-fan-control
install -m 755 "${SCRIPT_DIR}/core-fan-control" /usr/local/sbin/core-fan-control
# install -m 644 bootstrap/core-fan.service /etc/systemd/system/core-fan.service
install -m 644 "${SCRIPT_DIR}/core-fan.service" /etc/systemd/system/core-fan.service

# systemctl daemon-reload
# systemctl enable --now core-fan.service
systemctl daemon-reload
systemctl enable core-fan.service

pwm_present=0
if compgen -G '/sys/devices/platform/cooling_fan/hwmon/hwmon*/pwm1' >/dev/null; then
  pwm_present=1
fi

if [[ "${pwm_present}" -eq 1 ]]; then
  systemctl restart core-fan.service
  sleep 2
  echo "core-fan.service is active. journalctl -u core-fan -f"
  journalctl -u core-fan -n 8 --no-pager || true
else
  need_reboot=1
  echo "cooling_fan pwm1 is not in sysfs yet. Reboot so dtparam=cooling_fan=on loads."
  echo "After reboot the service starts on its own."
fi

if [[ "${need_reboot}" -eq 1 ]]; then
  echo "Reboot Core to take PWM (without it the P12 Pro stays full speed)."
fi
