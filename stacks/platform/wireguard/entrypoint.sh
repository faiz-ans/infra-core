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
exec /usr/bin/dumb-init node server/index.mjs
