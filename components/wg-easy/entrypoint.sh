#!/bin/sh
# Wrappers translate wg and wg-quick into helper operations. Key generation
# stays in this container. The helper owns NAT, so this process does not
# call iptables.
set -e
export PATH="/opt/wg-handoff/bin:/usr/sbin:/sbin:/usr/bin:/bin:${PATH}"
sock="${WG_HELPER_SOCK:-/etc/wireguard/.wg-helper.sock}"
i=0
while [ ! -S "${sock}" ]; do
  i=$((i + 1))
  if [ "${i}" -gt 30 ]; then
    echo "wg-helper socket ${sock} is not ready" >&2
    exit 1
  fi
  sleep 1
done

# Record the egress device in SQLite. NAT is applied when the helper brings wg0 up.
if [ -f /seed-mtu.mjs ] && [ -f /etc/wireguard/wg-easy.db ]; then
  SEED_IPTABLES=0 node /seed-mtu.mjs || true
fi

(
  i=0
  while [ "${i}" -lt 30 ]; do
    if grep -q '^ *wg0:' /proc/net/dev 2>/dev/null; then
      sleep 1
      if [ -f /seed-mtu.mjs ]; then
        SEED_IPTABLES=0 node /seed-mtu.mjs || true
      fi
      break
    fi
    i=$((i + 1))
    sleep 1
  done
) &

exec /usr/bin/dumb-init node server/index.mjs
