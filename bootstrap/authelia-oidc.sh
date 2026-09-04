#!/usr/bin/env bash
# Existing Core: generate Authelia OIDC material and household users.
# Run as root on Core (needs docker + DATA_ROOT).
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-... DOMAIN=home.lan bash bootstrap/authelia-oidc.sh
#
# New installs: core.sh does the same work. This script is the migration path
# when users.yml still has the bootstrap 'admin' user.

set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

: "${DATA_ROOT:?Set DATA_ROOT to the OMV data mount}"
: "${DOMAIN:?Set DOMAIN (same value as Komodo DOMAIN)}"

DIR="${DATA_ROOT}/system/authelia"
mkdir -p "${DIR}"

# Gitea (and other Go clients) need the Caddy tls-internal CA as a file.
# If this path is a directory, Docker already hit the missing-file mount trap.
if [[ -d "${DIR}/caddy-root.crt" ]]; then
  rm -rf "${DIR}/caddy-root.crt"
fi
if docker ps -qf name=^caddy$ | grep -q .; then
  docker exec caddy cat /data/caddy/pki/authorities/local/root.crt > "${DIR}/caddy-root.crt"
  chmod 644 "${DIR}/caddy-root.crt"
  echo "Wrote ${DIR}/caddy-root.crt"
  if [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
    cat /etc/ssl/certs/ca-certificates.crt "${DIR}/caddy-root.crt" > "${DIR}/ca-bundle.crt"
  else
    cp "${DIR}/caddy-root.crt" "${DIR}/ca-bundle.crt"
  fi
  chmod 644 "${DIR}/ca-bundle.crt"
  echo "Wrote ${DIR}/ca-bundle.crt"
else
  echo "Caddy is not running; skip caddy-root.crt (dump it later — see bootstrap/gitea.md)."
fi

hash_password() {
  local password="$1" digest
  digest=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate argon2 --password "${password}" \
    | awk '/^Digest:/ {print $2}')
  if [[ -z "${digest}" ]]; then
    digest="\$plaintext\$${password}"
  fi
  printf '%s' "${digest}"
}

if [[ ! -f "${DIR}/oidc.pem" ]]; then
  tmp=$(mktemp -d)
  docker run --rm -v "${tmp}:/out" authelia/authelia:4 \
    authelia crypto pair rsa generate --directory /out
  if [[ -f "${tmp}/private.pem" ]]; then
    cp "${tmp}/private.pem" "${DIR}/oidc.pem"
  elif [[ -f "${tmp}/key.pem" ]]; then
    cp "${tmp}/key.pem" "${DIR}/oidc.pem"
  else
    echo "authelia crypto pair rsa generate did not write a private key in ${tmp}:"
    ls -la "${tmp}"
    exit 1
  fi
  rm -rf "${tmp}"
  chmod 600 "${DIR}/oidc.pem"
  echo "Wrote ${DIR}/oidc.pem"
else
  echo "Keeping existing ${DIR}/oidc.pem"
fi

if [[ ! -f "${DIR}/client_secret_digest" ]] || [[ ! -s "${DIR}/client_secret" ]]; then
  PLAIN=$(openssl rand -hex 32)
  DIGEST=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate pbkdf2 --variant sha512 --password "${PLAIN}" \
    | awk '/^Digest:/ {print $2}')
  if [[ -z "${DIGEST}" ]]; then
    echo "Failed to hash OIDC client secret."
    exit 1
  fi
  printf '%s' "${PLAIN}" > "${DIR}/client_secret"
  printf '%s' "${DIGEST}" > "${DIR}/client_secret_digest"
  chmod 600 "${DIR}/client_secret" "${DIR}/client_secret_digest"
  echo "Wrote OIDC client secret (plaintext + digest)."
else
  PLAIN=$(cat "${DIR}/client_secret")
  echo "Keeping existing OIDC client secret."
fi

HMAC=$(openssl rand -hex 32)
if [[ -f /etc/komodo/core.config.toml ]] && grep -q '^AUTHELIA_OIDC_HMAC_SECRET' /etc/komodo/core.config.toml; then
  HMAC=$(awk -F '"' '/^AUTHELIA_OIDC_HMAC_SECRET/ {print $2; exit}' /etc/komodo/core.config.toml)
  echo "Reusing AUTHELIA_OIDC_HMAC_SECRET from core.config.toml"
fi

read -r -s -p "Authelia password for faiz: " FAIZ_PW
echo
read -r -s -p "Authelia password for diana: " DIANA_PW
echo
if [[ -z "${FAIZ_PW}" || -z "${DIANA_PW}" ]]; then
  echo "Both passwords are required."
  exit 1
fi

FAIZ_HASH=$(hash_password "${FAIZ_PW}")
DIANA_HASH=$(hash_password "${DIANA_PW}")

if [[ -f "${DIR}/users.yml" ]]; then
  cp -a "${DIR}/users.yml" "${DIR}/users.yml.bak.$(date +%Y%m%d%H%M%S)"
fi

cat > "${DIR}/users.yml" <<EOF
users:
  faiz:
    disabled: false
    displayname: 'Faiz'
    password: '${FAIZ_HASH}'
    email: 'faiz@${DOMAIN}'
    groups:
      - admins
      - users
  diana:
    disabled: false
    displayname: 'Diana'
    password: '${DIANA_HASH}'
    email: 'diana@${DOMAIN}'
    groups:
      - users
EOF
chmod 644 "${DIR}/users.yml"

echo
echo "Add these Komodo secrets (Settings → Secrets). Mark them secrets."
echo "  AUTHELIA_OIDC_HMAC_SECRET = ${HMAC}"
echo "  OIDC_CLIENT_SECRET        = ${PLAIN}"
echo
echo "If this host already has /etc/komodo/core.config.toml, also append those"
echo "two keys there so a later core.sh re-run keeps them."
echo
echo "Then Redeploy: authelia, caddy, opencloud, gitea, jotty, linkding, bytestash,"
echo "homepage, transmute, monitoring. Recreate Komodo Core after editing"
echo "/etc/komodo/bootstrap/compose.env (see bootstrap/authelia.md)."
echo
echo "Gitea, Immich, and Adventure Log still need a one-time OIDC click in their UI"
echo "(or the gitea admin auth command). Built-in admin accounts stay as break-glass."
