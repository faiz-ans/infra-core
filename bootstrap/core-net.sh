#!/usr/bin/env bash
# Host forwarding + IPv6 off. Safe to re-run (does not restart Docker).
# ip_forward / src_valid_mark: WireGuard NAT. IPv6 off: Docker must not
# prefer a dual-stack `edge` as the container default gateway (GitHub DNS).
#
#   sudo bash bootstrap/core-net.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

cat > /etc/sysctl.d/99-komodo-net.conf <<'EOF'
net.ipv4.ip_forward=1
net.ipv4.conf.all.src_valid_mark=1
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
EOF

# Drop the older single-key file if present.
rm -f /etc/sysctl.d/99-ip-forward.conf

sysctl --system >/dev/null
sysctl net.ipv4.ip_forward net.ipv4.conf.all.src_valid_mark \
  net.ipv6.conf.all.disable_ipv6

echo "Default IPv4 route:"
ip -4 route show default || true
echo "Apply docker ipv6 false with: sudo bash bootstrap/core-docker-engine.sh"
echo "Then Redeploy wireguard so seed-mtu.mjs rewrites NAT to this iface."
