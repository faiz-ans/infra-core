#!/usr/bin/env bash
# OMV NUT for a USB CyberPower ST625U: monitor the UPS and shut Core down
# when the battery is low. Safe to re-run.
#
#   sudo bash bootstrap/omv/omv-nut.sh
#
# Plug the NAS into a *battery-backed* outlet (ST625U: four of eight). The
# USB HID cable is the communication port, not a charge-only USB-A.
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

if ! command -v omv-rpc >/dev/null 2>&1; then
  echo "omv-rpc not found."
  exit 1
fi

UPSNAME="${UPSNAME:-ups}"
COMMENT="${COMMENT:-CyberPower ST625U}"
# fsd = Workbench "UPS reaches low battery" (not "UPS goes on battery").
SHUTDOWNMODE="${SHUTDOWNMODE:-fsd}"
SHUTDOWNTIMER="${SHUTDOWNTIMER:-30}"
# CyberPower HID often reports battery.charge.low=0, which never trips LB.
CHARGE_LOW="${CHARGE_LOW:-30}"
NUT_REMOTE_USER="${NUT_REMOTE_USER:-peanut}"
ANSWERS="${ANSWERS:-/etc/infra-core/bootstrap-answers.env}"
SITE_ENV="${SITE_ENV:-/etc/infra-core/site.env}"

# PeaNUT is host-net and talks to upsd at 127.0.0.1:3493. Remote monitoring
# still makes upsd LISTEN beyond localhost. Password is NUT_REMOTE_PASSWORD
# (do not WAN-forward 3493).
if [[ -z "${NUT_REMOTE_PASSWORD:-}" && -f "${SITE_ENV}" ]]; then
  # shellcheck disable=SC1090
  source "${SITE_ENV}"
fi
if [[ -z "${NUT_REMOTE_PASSWORD:-}" && -f "${ANSWERS}" ]]; then
  # shellcheck disable=SC1090
  source "${ANSWERS}"
fi
if [[ -z "${NUT_REMOTE_PASSWORD:-}" ]]; then
  NUT_REMOTE_PASSWORD=$(openssl rand -hex 16)
  echo "Generated NUT_REMOTE_PASSWORD (not printed). Keep it in ${ANSWERS}."
fi
mkdir -p "$(dirname "${ANSWERS}")"
if [[ -f "${ANSWERS}" ]] && grep -qE '^NUT_REMOTE_PASSWORD=' "${ANSWERS}"; then
  sed -i "s|^NUT_REMOTE_PASSWORD=.*|NUT_REMOTE_PASSWORD='${NUT_REMOTE_PASSWORD}'|" "${ANSWERS}"
else
  printf "NUT_REMOTE_PASSWORD='%s'\n" "${NUT_REMOTE_PASSWORD}" >> "${ANSWERS}"
fi
export NUT_REMOTE_PASSWORD NUT_REMOTE_USER

# apt-get update
# apt-get install -y openmediavault-nut usbutils
export DEBIAN_FRONTEND=noninteractive
if dpkg -s openmediavault-nut >/dev/null 2>&1; then
  echo "openmediavault-nut already installed; skipping apt."
else
  apt-get update -qq
  apt-get install -y openmediavault-nut usbutils
fi

# Plugin RPC lands after engined reloads.
# systemctl restart openmediavault-engined
systemctl restart openmediavault-engined
sleep 2

# udevadm control --reload-rules
# udevadm trigger
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger 2>/dev/null || true

vendorid=""
productid=""
# lsusb -d 0764:
# CyberPower vendor id is 0764.
if command -v lsusb >/dev/null 2>&1; then
  lsusb || true
  usb_line=$(lsusb -d 0764: 2>/dev/null | head -n 1 || true)
  if [[ -z "${usb_line}" ]]; then
    usb_line=$(lsusb 2>/dev/null | grep -iE 'Cyber.?Power|CPS ' | head -n 1 || true)
  fi
  if [[ "${usb_line}" =~ ID[[:space:]]+([0-9a-fA-F]{4}):([0-9a-fA-F]{4}) ]]; then
    vendorid="${BASH_REMATCH[1],,}"
    productid="${BASH_REMATCH[2],,}"
    echo "USB UPS ${vendorid}:${productid}"
  else
    echo "No CyberPower USB HID device yet (lsusb). Driver will retry. Cable is the HID port, not a charge USB-A."
  fi
fi

python3 - "${UPSNAME}" "${COMMENT}" "${SHUTDOWNMODE}" "${SHUTDOWNTIMER}" "${CHARGE_LOW}" "${vendorid}" "${productid}" "${NUT_REMOTE_USER}" <<'PY'
import json, os, subprocess, sys, time

upsname, comment, shutdownmode, shutdowntimer, charge_low, vendorid, productid, remoteuser = sys.argv[1:]
remotepassword = os.environ.get("NUT_REMOTE_PASSWORD") or ""
if not remotepassword:
    raise SystemExit("NUT_REMOTE_PASSWORD empty")

lines = [
    "driver = usbhid-ups",
    "port = auto",
    "pollinterval = 2",
    # CPS treats offdelay/ondelay in minutes internally; 60/120 is the NUT default.
    "offdelay = 60",
    "ondelay = 120",
    f"override.battery.charge.low = {charge_low}",
]
if vendorid and productid:
    lines.append(f"vendorid = {vendorid}")
    lines.append(f"productid = {productid}")
driverconf = "\n".join(lines) + "\n"


def rpc(service, method, params=None):
    cmd = ["omv-rpc", "-u", "admin", service, method]
    if params is not None:
        cmd.append(json.dumps(params))
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out) if out.strip() else None


current = {}
last = None
for _ in range(15):
    try:
        current = rpc("Nut", "get") or {}
        last = None
        break
    except subprocess.CalledProcessError as e:
        last = e
        time.sleep(1)
if last is not None:
    raise SystemExit("Nut RPC not ready after plugin install. systemctl status openmediavault-engined")

payload = {
    "enable": True,
    "mode": "standalone",
    "upsname": upsname,
    "comment": comment,
    "netclienthostname": current.get("netclienthostname") or "",
    "netclientusername": current.get("netclientusername") or "",
    "netclientpassword": current.get("netclientpassword") or "",
    "powervalue": int(current.get("powervalue") or 1),
    "driverconf": driverconf,
    "shutdownmode": shutdownmode,
    "shutdowntimer": int(shutdowntimer),
    "remotemonitor": True,
    "remoteuser": remoteuser,
    "remotepassword": remotepassword,
}
rpc("Nut", "set", payload)
print(f"NUT {upsname}: standalone usbhid-ups, shutdownmode={shutdownmode}, charge.low={charge_low}, remotemonitor user={remoteuser}")
PY

# omv-salt deploy run nut
# Salt also runs `monit monitor nut-server|nut-monitor`. Those checks do not
# exist until the monit module is applied, so the first nut deploy can fail
# after NUT itself is already running.
set +e
omv-salt deploy run nut
nut_salt_rc=$?
omv-salt deploy run monit
set -e

# systemctl restart nut-driver-enumerator nut-server nut-monitor
systemctl restart nut-driver-enumerator 2>/dev/null || true
systemctl restart nut-server 2>/dev/null || true
systemctl restart nut-monitor 2>/dev/null || true

if ! systemctl is-active --quiet nut-server || ! systemctl is-active --quiet nut-monitor; then
  echo "nut-server / nut-monitor did not start (salt rc ${nut_salt_rc})."
  systemctl --no-pager --full status nut-server nut-monitor "nut-driver@${UPSNAME}" || true
  exit 1
fi
if [[ "${nut_salt_rc}" -ne 0 ]]; then
  echo "omv-salt deploy run nut reported failures (usually monit has no nut-* checks yet). nut-server and nut-monitor are active."
fi

echo
echo "Waiting for upsc ${UPSNAME}..."
ok=0
for _ in $(seq 1 20); do
  if upsc "${UPSNAME}" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if [[ "${ok}" -eq 1 ]]; then
  upsc "${UPSNAME}" || true
  echo
  echo "Want ups.status OL (or OL CHRG). battery.charge.low should be ${CHARGE_LOW}."
else
  echo "upsc ${UPSNAME} is not ready. journalctl -u 'nut-driver@${UPSNAME}' -n 40 --no-pager"
  systemctl --no-pager --full status "nut-driver@${UPSNAME}" 2>/dev/null || true
  journalctl -u "nut-driver@${UPSNAME}" -n 40 --no-pager || true
fi

echo
echo "Workbench: Services → UPS. Diagnostics → Services → UPS."
echo "Do not run upsmon -c fsd unless you mean to shut this host down."
echo "See bootstrap/omv/omv-nut.md"
