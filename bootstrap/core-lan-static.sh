#!/usr/bin/env bash
# Pin Core's LAN IPv4 on the uplink NIC. Safe to re-run. Does not restart Docker.
# Do not rely on a router DHCP reservation: a USB 2.5G NIC can have carrier
# while NetworkManager never binds a lease (no SSH, nothing in the DHCP list).
#
#   sudo bash bootstrap/core-lan-static.sh
#   sudo NAS_LAN_IP=192.168.1.110 NAS_LAN_GW=192.168.1.1 bash bootstrap/core-lan-static.sh
#
# Uses the live uplink (default IPv4 route). Refuses to change the address if
# NAS_LAN_IP does not already match that iface (would drop SSH).
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

ENV_FILE=/etc/komodo/bootstrap/compose.env
ANSWERS=/etc/komodo/bootstrap-answers.env

is_lan_iface() {
  local d=$1
  case "${d}" in
    ''|lo|docker*|br-*|veth*|wg*|tun*|tap*|virbr*|cni*|flannel*|wlan*|wlx*)
      return 1
      ;;
  esac
  return 0
}

from_kv_file() {
  local file=$1 key=$2
  [[ -f "${file}" ]] || return 0
  awk -F= -v k="${key}" '
    $1==k {
      gsub(/["'\'' ]/, "", $2)
      print $2
      exit
    }
  ' "${file}"
}

route_field() {
  local token=$1
  ip -4 route get 1.1.1.1 2>/dev/null \
    | awk -v t="${token}" '{for (i=1;i<=NF;i++) if ($i==t) {print $(i+1); exit}}'
}

if [[ -z "${NAS_LAN_IP:-}" ]]; then
  NAS_LAN_IP=$(from_kv_file "${ENV_FILE}" NAS_LAN_IP)
fi
if [[ -z "${NAS_LAN_IP:-}" ]]; then
  NAS_LAN_IP=$(from_kv_file "${ANSWERS}" NAS_LAN_IP)
fi

live_ip=$(route_field src)
live_dev=$(route_field dev)
live_gw=$(route_field via)

if [[ -z "${NAS_LAN_IP:-}" ]]; then
  NAS_LAN_IP=${live_ip}
fi
if [[ -z "${NAS_LAN_IP:-}" ]]; then
  echo "core-lan-static: no NAS_LAN_IP (set it, or have an IPv4 default route)."
  exit 1
fi

iface=${NAS_LAN_IFACE:-}
if [[ -z "${iface}" ]]; then
  iface=$(ip -4 -o addr show | awk -v ip="${NAS_LAN_IP}" 'index($4, ip "/")==1 {print $2; exit}')
fi
if [[ -z "${iface}" ]]; then
  iface=${live_dev}
fi
if ! is_lan_iface "${iface}"; then
  echo "core-lan-static: uplink '${iface:-none}' is not a LAN NIC."
  ip -4 route show default || true
  ip -4 -o addr show || true
  exit 1
fi

if [[ -n "${live_ip}" && "${NAS_LAN_IP}" != "${live_ip}" ]]; then
  echo "core-lan-static: NAS_LAN_IP=${NAS_LAN_IP} but ${iface} is ${live_ip}."
  echo "Refusing to change the address (that drops SSH). Re-run with NAS_LAN_IP=${live_ip}."
  exit 1
fi

gw=${NAS_LAN_GW:-${live_gw}}
if [[ -z "${gw}" ]]; then
  echo "core-lan-static: no gateway (default route via, or NAS_LAN_GW=)."
  exit 1
fi

pfx=${NAS_LAN_PREFIX:-}
if [[ -z "${pfx}" ]]; then
  pfx=$(ip -4 -o addr show dev "${iface}" \
    | awk -v ip="${NAS_LAN_IP}" 'index($4, ip "/")==1 {split($4, a, "/"); print a[2]; exit}')
fi
if [[ -z "${pfx}" ]]; then
  pfx=$(ip -4 -o addr show dev "${iface}" | awk '$3=="inet" {split($4, a, "/"); print a[2]; exit}')
fi
pfx=${pfx:-24}
cidr="${NAS_LAN_IP}/${pfx}"

if ! command -v nmcli >/dev/null 2>&1; then
  echo "core-lan-static: nmcli not found (NetworkManager). OMV install must use -n."
  exit 1
fi
systemctl start NetworkManager 2>/dev/null || true

if command -v dhcpcd >/dev/null 2>&1; then
  dhcpcd -x "${iface}" 2>/dev/null || dhcpcd -x 2>/dev/null || true
fi
systemctl disable --now dhcpcd 2>/dev/null || true
systemctl disable --now dhcpcd.service 2>/dev/null || true

nmcli device set "${iface}" managed yes 2>/dev/null || true
con=$(nmcli -g GENERAL.CONNECTION device show "${iface}" 2>/dev/null || true)
if [[ "${con}" == "--" ]]; then
  con=""
fi
if [[ -z "${con}" ]]; then
  con=$(nmcli -t -f NAME,DEVICE connection show --active \
    | awk -F: -v d="${iface}" '$2==d {print $1; exit}')
fi
if [[ -z "${con}" ]]; then
  con=$(nmcli -t -f NAME,DEVICE connection show \
    | awk -F: -v d="${iface}" '$2==d {print $1; exit}')
fi

want_method=manual
already=0
if [[ -n "${con}" ]]; then
  cur_method=$(nmcli -g ipv4.method connection show "${con}" 2>/dev/null || true)
  cur_addr=$(nmcli -g ipv4.addresses connection show "${con}" 2>/dev/null | awk -F, '{print $1; exit}')
  cur_addr=${cur_addr// /}
  cur_gw=$(nmcli -g ipv4.gateway connection show "${con}" 2>/dev/null || true)
  if [[ "${cur_method}" == "${want_method}" && "${cur_addr}" == "${cidr}" && "${cur_gw}" == "${gw}" ]]; then
    already=1
  fi
fi

if [[ "${already}" -eq 1 ]]; then
  echo "core-lan-static: ${con} already ${cidr} via ${gw} on ${iface} (manual)."
else
  if [[ -z "${con}" ]]; then
    con=core-lan
    echo "core-lan-static: adding ${con} ${cidr} via ${gw} on ${iface}"
    # nmcli connection add type ethernet con-name core-lan ifname eth1 ipv4.method manual ...
    nmcli connection add type ethernet con-name "${con}" ifname "${iface}" \
      ipv4.method manual \
      ipv4.addresses "${cidr}" \
      ipv4.gateway "${gw}" \
      ipv4.ignore-auto-dns yes \
      ipv6.method disabled \
      connection.autoconnect yes \
      connection.interface-name "${iface}"
  else
    echo "core-lan-static: ${con} → ${cidr} via ${gw} on ${iface} (manual)"
    # nmcli connection modify "Wired connection 1" ipv4.method manual ...
    nmcli connection modify "${con}" \
      ipv4.method manual \
      ipv4.addresses "${cidr}" \
      ipv4.gateway "${gw}" \
      ipv4.ignore-auto-dns yes \
      ipv6.method disabled \
      connection.autoconnect yes \
      connection.interface-name "${iface}"
  fi
  nmcli connection up "${con}"
fi

if ! ip -4 addr show dev "${iface}" | grep -q "inet ${NAS_LAN_IP}/"; then
  echo "core-lan-static: ${NAS_LAN_IP} is not on ${iface} after apply."
  ip -4 -br addr show "${iface}" || true
  exit 1
fi
if ! ip -4 route show default | grep -q "via ${gw} dev ${iface}"; then
  echo "core-lan-static: default via ${gw} dev ${iface} missing."
  ip -4 route show default || true
  exit 1
fi

echo "core-lan-static: ${iface} ${cidr} via ${gw} (NetworkManager manual, DNS via systemd-resolved)."
ip -4 -br addr show "${iface}"
ip -4 route show default
