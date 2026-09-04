#!/bin/sh
# Copy Caddy tls internal root to DATA_ROOT so Gitea/Komodo can trust
# https://auth.${DOMAIN}. Backgrounded from the caddy container; never
# fail the proxy.
dest="${CA_EXPORT_DIR:-/export-ca}"
src=/data/caddy/pki/authorities/local/root.crt

i=0
while [ "$i" -lt 90 ]; do
  if [ -f "$src" ]; then
    if [ -d "${dest}/caddy-root.crt" ]; then
      rm -rf "${dest}/caddy-root.crt"
    fi
    if [ -d "${dest}/ca-bundle.crt" ]; then
      rm -rf "${dest}/ca-bundle.crt"
    fi
    if ! cp "$src" "${dest}/caddy-root.crt"; then
      echo "caddy-ca: could not write ${dest}/caddy-root.crt"
      exit 0
    fi
    chmod 644 "${dest}/caddy-root.crt" || true
    if [ -f /etc/ssl/certs/ca-certificates.crt ]; then
      cat /etc/ssl/certs/ca-certificates.crt "${dest}/caddy-root.crt" > "${dest}/ca-bundle.crt" || true
    else
      cp "${dest}/caddy-root.crt" "${dest}/ca-bundle.crt" || true
    fi
    chmod 644 "${dest}/ca-bundle.crt" || true
    echo "caddy-ca: exported ${dest}/caddy-root.crt"
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done
echo "caddy-ca: ${src} not ready; skip (caddy stays up)"
exit 0
