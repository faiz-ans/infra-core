#!/bin/bash
# Force the published WebUI port and reverse-proxy settings on every start.
# An older qBittorrent.conf (Port=8080, host-header check) makes Caddy's :8081 look dead.
set -e
for CONF in /config/qBittorrent/qBittorrent.conf /config/qBittorrent.conf; do
  [ -f "${CONF}" ] || continue
  sed -i 's/^WebUI\\Port=.*/WebUI\\Port=8081/' "${CONF}"
  sed -i 's/^WebUI\\Address=.*/WebUI\\Address=*/' "${CONF}"
  sed -i 's/^WebUI\\HostHeaderValidation=.*/WebUI\\HostHeaderValidation=false/' "${CONF}"
  grep -q '^WebUI\\HostHeaderValidation=' "${CONF}" || printf '%s\n' 'WebUI\HostHeaderValidation=false' >> "${CONF}"
  sed -i 's/^WebUI\\CSRFProtection=.*/WebUI\\CSRFProtection=false/' "${CONF}"
  grep -q '^WebUI\\CSRFProtection=' "${CONF}" || printf '%s\n' 'WebUI\CSRFProtection=false' >> "${CONF}"
  sed -i 's/^WebUI\\ReverseProxySupportEnabled=.*/WebUI\\ReverseProxySupportEnabled=true/' "${CONF}"
  grep -q '^WebUI\\ReverseProxySupportEnabled=' "${CONF}" || printf '%s\n' 'WebUI\ReverseProxySupportEnabled=true' >> "${CONF}"
done
