#!/bin/sh
# Copy Caddy tls internal root to DATA_ROOT so Gitea/Komodo can trust
# https://auth.${DOMAIN}. Run as a sidecar to `caddy run`.
set -eu
dest="${CA_EXPORT_DIR:-/export-ca}"
src=/data/caddy/pki/authorities/local/root.crt

i=0
while [ "$i" -lt 60 ]; do
  if [ -f "$src" ]; then
    if [ -d "${dest}/caddy-root.crt" ]; then
      rm -rf "${dest}/caddy-root.crt"
    fi
    if [ -d "${dest}/ca-bundle.crt" ]; then
      rm -rf "${dest}/ca-bundle.crt"
    fi
    cp "$src" "${dest}/caddy-root.crt"
    chmod 644 "${dest}/caddy-root.crt"
    if [ -f /etc/ssl/certs/ca-certificates.crt ]; then
      cat /etc/ssl/certs/ca-certificates.crt "${dest}/caddy-root.crt" > "${dest}/ca-bundle.crt"
    else
      cp "${dest}/caddy-root.crt" "${dest}/ca-bundle.crt"
    fi
    chmod 644 "${dest}/ca-bundle.crt"
    echo "caddy-ca: exported ${dest}/caddy-root.crt"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done
echo "caddy-ca: ${src} not ready after 60s"
exit 1
