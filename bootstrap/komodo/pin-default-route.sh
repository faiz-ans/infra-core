#!/bin/sh
# Pin Core's default IPv4 route to the compose `default` network (the iface
# used to reach ferretdb). Dual-homed Core otherwise lets `edge` steal the
# gateway; Docker DNS then fails for github.com and ResourceSync reports
# "Found file errors." Engine gw_priority / compose priority do not stay
# correct across every recreate and reboot.
#
# Runs in Core's netns (compose service core-route). Needs NET_ADMIN.
set -eu

sleep_s="${PIN_ROUTE_INTERVAL:-15}"

ferretdb_ip() {
  getent hosts ferretdb 2>/dev/null | awk '{print $1; exit}'
}

route_dev_for() {
  ip route get "$1" 2>/dev/null | awk '{
    for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }
  }'
}

via_for_dev() {
  # Docker bridge gateway is the first host in the iface subnet.
  addr=$(ip -4 -o addr show dev "$1" 2>/dev/null | awk '{print $4; exit}')
  [ -n "${addr:-}" ] || return 1
  ip=${addr%/*}
  p=${addr#*/}
  a=${ip%%.*}
  rest=${ip#*.}
  b=${rest%%.*}
  rest=${rest#*.}
  c=${rest%%.*}
  case $p in
    8) echo "$a.0.0.1" ;;
    16) echo "$a.$b.0.1" ;;
    24) echo "$a.$b.$c.1" ;;
    *) echo "$a.$b.$c.1" ;;
  esac
}

default_dev() {
  ip route | awk '/^default/ {
    for (i = 1; i <= NF; i++) if ($i == "dev") { print $(i + 1); exit }
  }'
}

default_count() {
  ip route | awk '/^default/ { n++ } END { print n + 0 }'
}

pin() {
  fe=$(ferretdb_ip) || true
  [ -n "${fe:-}" ] || return 0
  good=$(route_dev_for "$fe") || true
  [ -n "${good:-}" ] || return 0
  via=$(via_for_dev "$good") || true
  [ -n "${via:-}" ] || return 0
  now=$(default_dev || true)
  n=$(default_count)
  if [ "${now:-}" = "$good" ] && [ "$n" -le 1 ]; then
    return 0
  fi
  while ip route del default 2>/dev/null; do :; done
  ip route add default via "$via" dev "$good"
}

echo "core-route: pinning default via ferretdb iface every ${sleep_s}s"
while true; do
  pin || true
  sleep "$sleep_s"
done
