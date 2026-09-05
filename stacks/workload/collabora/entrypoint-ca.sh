#!/bin/bash
# Collabora WOPI CheckFileInfo calls https://cloud.${DOMAIN}. Caddy uses
# tls internal; recent CODE still verifies that cert even with
# ssl.ssl_verification=false. Fetch the CA Caddy already publishes and
# install it, then start CODE.
set -euo pipefail

CA_URL="${CADDY_CA_URL:?set CADDY_CA_URL in compose}"
CA_DST=/usr/local/share/ca-certificates/caddy-local.crt

i=0
while [ "$i" -lt 8 ]; do
  if command -v curl >/dev/null 2>&1; then
    if curl -kfsSL --max-time 5 "${CA_URL}" -o "${CA_DST}"; then
      break
    fi
  elif command -v wget >/dev/null 2>&1; then
    if wget --no-check-certificate -q --timeout=5 -O "${CA_DST}" "${CA_URL}"; then
      break
    fi
  else
    echo "collabora-ca: no curl/wget; skip CA install" >&2
    break
  fi
  i=$((i + 1))
  sleep 2
done

if [ -s "${CA_DST}" ]; then
  update-ca-certificates >/dev/null 2>&1 || true
  echo "collabora-ca: installed ${CA_DST}"
else
  echo "collabora-ca: could not fetch ${CA_URL}; WOPI may fail tls internal" >&2
fi

export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}"
exec /start-collabora-online.sh
