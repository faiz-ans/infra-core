#!/bin/sh
set -eu
# Expand compose env into dnsmasq wildcard (Pi-hole does not interpolate this file itself).
sed -e "s|\${DOMAIN}|${DOMAIN}|g" -e "s|\${NAS_LAN_IP}|${NAS_LAN_IP}|g" \
  /etc/dnsmasq.d/99-wildcard.template > /etc/dnsmasq.d/99-wildcard.conf
