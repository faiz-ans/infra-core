#!/bin/bash
# Register Authelia as a Gitea OAuth source. Idempotent. Always exit 0 so
# a missing CA or Authelia cannot restart Gitea.
if [[ -z "${OIDC_CLIENT_SECRET:-}" || -z "${DOMAIN:-}" ]]; then
  echo "gitea-oidc: skip (OIDC_CLIENT_SECRET or DOMAIN unset)"
  exit 0
fi

ca=/etc/ssl/caddy/caddy-root.crt
if ! grep -q "BEGIN CERTIFICATE" "${ca}" 2>/dev/null; then
  echo "gitea-oidc: Caddy CA not ready at ${ca}; skip"
  exit 0
fi

config=/data/gitea/conf/app.ini
if [[ ! -f "${config}" ]]; then
  echo "gitea-oidc: ${config} missing; skip"
  exit 0
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
if [[ "${status}" -eq 0 ]] || echo "${out}" | grep -qiE 'already exist|duplicate'; then
  echo "gitea-oidc: registered authelia"
  exit 0
fi
echo "gitea-oidc: ${out}"
exit 0
