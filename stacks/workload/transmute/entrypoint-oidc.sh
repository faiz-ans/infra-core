#!/bin/bash
# Trust Caddy tls internal so Python/httpx can discover Authelia over HTTPS.
# Immich can set NODE_TLS_REJECT_UNAUTHORIZED; Transmute cannot.
set -e
AUTH="${OIDC_ISSUER_URL%/}"
if [ -n "${AUTH}" ]; then
  wget -q --no-check-certificate -O /tmp/caddy-root.crt "${AUTH}/pki/local-root.crt" || true
  if grep -q "BEGIN CERTIFICATE" /tmp/caddy-root.crt 2>/dev/null; then
    export SSL_CERT_FILE=/tmp/caddy-root.crt
    export REQUESTS_CA_BUNDLE=/tmp/caddy-root.crt
    export CURL_CA_BUNDLE=/tmp/caddy-root.crt
  fi
fi
exec /bin/bash /app/entrypoint.sh
