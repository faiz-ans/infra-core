#!/bin/sh
# Fetch the site CA and write a WOPI proof key when OpenCloud is placed.
# Without CADDY_CA_URL this is a normal Collabora start.
set -eu
if [ -n "${CADDY_CA_URL:-}" ]; then
  if ! command -v curl >/dev/null 2>&1 || ! command -v openssl >/dev/null 2>&1; then
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl openssl
  fi
  if [ ! -s /ca/proof_key ]; then
    openssl genrsa -traditional -out /ca/proof_key.tmp 4096
    chown 1001:1001 /ca/proof_key.tmp 2>/dev/null || true
    chmod 400 /ca/proof_key.tmp
    mv /ca/proof_key.tmp /ca/proof_key
  fi
  i=0
  while [ "$i" -lt 30 ]; do
    if curl -kfsSL --max-time 5 "$CADDY_CA_URL" -o /ca/caddy-local.crt; then
      cat /etc/ssl/certs/ca-certificates.crt /ca/caddy-local.crt > /ca/ca-bundle.crt
      break
    fi
    i=$((i + 1))
    sleep 2
  done
  if [ ! -s /ca/ca-bundle.crt ]; then
    echo "collabora: Caddy CA not available at $CADDY_CA_URL" >&2
    exit 1
  fi
fi
exec /start-collabora-online.sh
