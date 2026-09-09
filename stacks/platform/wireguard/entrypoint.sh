#!/bin/sh
# Pi 6.18+ kernels have no ip_tables module. The image defaults to
# iptables-legacy, so wg-quick PostUp fails and deletes wg0.
set -e
if [ -x /usr/sbin/iptables-nft ]; then
  update-alternatives --install /usr/sbin/iptables iptables /usr/sbin/iptables-nft 20 \
    --slave /usr/sbin/iptables-restore iptables-restore /usr/sbin/iptables-nft-restore \
    --slave /usr/sbin/iptables-save iptables-save /usr/sbin/iptables-nft-save
  update-alternatives --install /usr/sbin/ip6tables ip6tables /usr/sbin/ip6tables-nft 20 \
    --slave /usr/sbin/ip6tables-restore ip6tables-restore /usr/sbin/ip6tables-nft-restore \
    --slave /usr/sbin/ip6tables-save ip6tables-save /usr/sbin/ip6tables-nft-save
fi

export PATH="/usr/sbin:/sbin:/usr/bin:/bin:${PATH}"

# Host netns: MASQUERADE survives docker stop. wg-easy PostUp always -A, so
# restart would duplicate unless we drop leftover 10.8.0.0/24 rules first.
flush_wg_masq() {
  n=0
  while [ "${n}" -lt 16 ]; do
    line=$(iptables -t nat -S POSTROUTING 2>/dev/null | grep MASQUERADE | grep -- '-s 10.8.0.0/24' | head -n 1 || true)
    [ -z "${line}" ] && break
    spec=${line#-A POSTROUTING }
    # shellcheck disable=SC2086
    iptables -t nat -D POSTROUTING ${spec} || break
    n=$((n + 1))
  done
}
flush_wg_masq

if [ -f /seed-mtu.mjs ] && [ -f /etc/wireguard/wg-easy.db ]; then
  node /seed-mtu.mjs || true
fi

# PostUp runs after node brings wg0 up (may still use -o eth0). Rewrite once
# the iface exists; do not keep adding rules — flush + one PostUp -A is enough.
(
  i=0
  while [ "${i}" -lt 30 ]; do
    if grep -q '^ *wg0:' /proc/net/dev 2>/dev/null; then
      sleep 1
      if [ -f /seed-mtu.mjs ]; then
        node /seed-mtu.mjs || true
      fi
      break
    fi
    i=$((i + 1))
    sleep 1
  done
) &

exec /usr/bin/dumb-init node server/index.mjs
