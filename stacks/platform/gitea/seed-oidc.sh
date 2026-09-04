#!/bin/bash
# Register Authelia as a Gitea OAuth source. Idempotent. Discovery needs
# the Caddy tls internal CA (export-ca.sh) and Authelia up.
set -euo pipefail

if [[ -z "${OIDC_CLIENT_SECRET:-}" || -z "${DOMAIN:-}" ]]; then
  echo "gitea-oidc: skip (OIDC_CLIENT_SECRET or DOMAIN unset)"
  exit 0
fi

ca=/etc/ssl/caddy/caddy-root.crt
for _ in $(seq 1 60); do
  if grep -q "BEGIN CERTIFICATE" "${ca}" 2>/dev/null; then
    break
  fi
  sleep 2
done
if ! grep -q "BEGIN CERTIFICATE" "${ca}" 2>/dev/null; then
  echo "gitea-oidc: Caddy CA not ready at ${ca}"
  exit 1
fi

config=/data/gitea/conf/app.ini
if [[ ! -f "${config}" ]]; then
  echo "gitea-oidc: ${config} missing"
  exit 1
fi

run() {
  if command -v su-exec >/dev/null 2>&1; then
    su-exec git gitea --config "${config}" "$@"
  else
    gitea --config "${config}" "$@"
  fi
}

if run admin auth list 2>/dev/null | grep -qi authelia; then
  echo "gitea-oidc: authelia already registered"
  exit 0
fi

set +e
out=$(run admin auth add-oauth \
  --name=authelia \
  --provider=openidConnect \
  --key=gitea \
  --secret="${OIDC_CLIENT_SECRET}" \
  --auto-discover-url="https://auth.${DOMAIN}/.well-known/openid-configuration" \
  --scopes='openid email profile groups' 2>&1)
status=$?
set -e
if [[ "${status}" -eq 0 ]]; then
  echo "gitea-oidc: registered authelia"
  exit 0
fi
if echo "${out}" | grep -qiE 'already exist|duplicate'; then
  echo "gitea-oidc: authelia already registered"
  exit 0
fi
echo "${out}"
exit "${status}"
