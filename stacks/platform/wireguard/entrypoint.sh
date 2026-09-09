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

# After first init the DB exists: rewrite factory 1420 → 1280 before node starts.
if [ -f /seed-mtu.mjs ] && [ -f /etc/wireguard/wg-easy.db ]; then
  node /seed-mtu.mjs || true
fi

# Keep MASQUERADE on the current uplink. wg-easy PostUp rewrites -o eth0
# after our first seed, and a stale eth0 default wins inside the container.
(
  while true; do
    if [ -f /seed-mtu.mjs ] && [ -f /etc/wireguard/wg-easy.db ]; then
      node /seed-mtu.mjs || true
    fi
    sleep 15
  done
) &

exec /usr/bin/dumb-init node server/index.mjs
