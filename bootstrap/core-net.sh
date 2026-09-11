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
net.ipv4.conf.all.rp_filter=2
net.ipv4.conf.default.rp_filter=2
net.ipv4.conf.all.route_localnet=1
net.ipv4.conf.default.route_localnet=1
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
EOF

# Drop the older single-key file if present.
rm -f /etc/sysctl.d/99-ip-forward.conf

sysctl --system >/dev/null
sysctl net.ipv4.ip_forward net.ipv4.conf.all.src_valid_mark \
  net.ipv4.conf.all.rp_filter net.ipv4.conf.all.route_localnet \
  net.ipv6.conf.all.disable_ipv6

# macOS resolves the short hostname via mDNS (Bonjour), not the router's
# device nickname and not Windows LLMNR. Host IPv6-off leaves Avahi on a
# dead inet6 socket unless use-ipv6=no.
avahi_conf=/etc/avahi/avahi-daemon.conf
if [[ -f "${avahi_conf}" ]]; then
  avahi_kv() {
    local key=$1 val=$2
    if grep -q "^#\?${key}=" "${avahi_conf}"; then
      sed -i "s/^#\?${key}=.*/${key}=${val}/" "${avahi_conf}"
    elif grep -q '^\[server\]' "${avahi_conf}"; then
      sed -i "/^\[server\]/a ${key}=${val}" "${avahi_conf}"
    fi
  }
  avahi_kv use-ipv4 yes
  avahi_kv use-ipv6 no
  avahi_kv host-name "$(hostname -s)"
  avahi_kv publish-workstation yes
  if grep -q "^#\?deny-interfaces=" "${avahi_conf}"; then
    sed -i 's/^#\?deny-interfaces=.*/deny-interfaces=docker0/' "${avahi_conf}"
  fi
  if systemctl restart avahi-daemon 2>/dev/null; then
    echo "Avahi: $(hostname -s).local on IPv4 (macOS smb://$(hostname -s))."
  else
    echo "Restart avahi-daemon after checking ${avahi_conf}."
  fi
  systemctl try-restart nmbd wsdd2 2>/dev/null || true
fi

echo "Default IPv4 route:"
ip -4 route show default || true
echo "Apply docker ipv6 false with: sudo bash bootstrap/core-docker-engine.sh"
echo "Then Redeploy wireguard so seed-mtu.mjs rewrites NAT to this iface."

# Host/Docker DNS must not depend on LAN :53 REDIRECT. A DHCP lease (or a
# leftover resolv.conf) often sets nameserver NAS_LAN_IP; when docker/WG
# rebuilds iptables that REDIRECT vanishes and Core cannot resolve
# github.com while LAN still works via the HTPC Pi-hole. Query Pi-hole on
# 127.0.0.1:15353; fall back to public DNS so GitHub still works if
# Pi-hole is down. core-lan-static.sh sets ipv4.ignore-auto-dns.
if [[ -d /etc/systemd ]]; then
  install -d /etc/systemd/resolved.conf.d
  cat > /etc/systemd/resolved.conf.d/99-infra-core.conf <<'EOF'
[Resolve]
DNS=127.0.0.1:15353
FallbackDNS=1.1.1.1 8.8.8.8
EOF
  if [[ -f /run/systemd/resolve/stub-resolv.conf ]]; then
    ln -sfn /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
  fi
  systemctl reload-or-restart systemd-resolved 2>/dev/null || true
  resolvectl flush-caches 2>/dev/null || true
  echo "Host DNS: 127.0.0.1:15353 (Pi-hole), FallbackDNS 1.1.1.1"
fi
