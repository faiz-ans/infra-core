#!/bin/bash
# Transmute httpx uses certifi, not SSL_CERT_FILE. Fetch Caddy's tls-internal
# CA over 443 (LAN allows 443; OMV often blocks 80/9091 from the HTPC) and
# point httpx at a bundle that includes it.
set -e
CA=/tmp/caddy-root.crt
BUNDLE=/tmp/caddy-ca-bundle.crt
ISSUER="${OIDC_ISSUER_URL:?OIDC_ISSUER_URL is required}"
if wget -q --no-check-certificate -O "${CA}" "${ISSUER}/pki/local-root.crt" \
  && grep -q "BEGIN CERTIFICATE" "${CA}"; then
  if [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
    cat /etc/ssl/certs/ca-certificates.crt "${CA}" > "${BUNDLE}"
  else
    cp "${CA}" "${BUNDLE}"
  fi
  export SSL_CERT_FILE="${BUNDLE}"
  export REQUESTS_CA_BUNDLE="${BUNDLE}"
  export CURL_CA_BUNDLE="${BUNDLE}"
  echo "transmute-oidc: CA bundle ${BUNDLE}" >&2
else
  echo "transmute-oidc: could not fetch ${ISSUER}/pki/local-root.crt; httpx will skip verify" >&2
  rm -f "${CA}"
fi
HOOKS=/tmp/oidc-hooks
mkdir -p "${HOOKS}"
cp /oidc-sitecustomize.py "${HOOKS}/sitecustomize.py"
export PYTHONPATH="${HOOKS}${PYTHONPATH:+:${PYTHONPATH}}"
export TRANSMUTE_OIDC_CA="${BUNDLE:-}"
echo "transmute-oidc: PYTHONPATH sitecustomize ready" >&2
exec /bin/bash /app/entrypoint.sh
