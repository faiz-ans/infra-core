#!/usr/bin/env bash
# NAS Layer 0 bootstrap. Copy to the Pi (scp) and run as root.
# Every live command is also shown in a nearby comment for copy-paste.

set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

KOMODO_DIR=/etc/komodo
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_BOOTSTRAP="${SCRIPT_DIR}"
# If you copied only this script, set REPO_BOOTSTRAP to a clone of infra-core/bootstrap.

prompt() {
  local var="$1" message="$2" default="${3:-}"
  local value
  if [[ -n "${default}" ]]; then
    read -r -p "${message} [${default}]: " value
    value="${value:-${default}}"
  else
    read -r -p "${message}: " value
  fi
  printf -v "${var}" '%s' "${value}"
}

prompt_secret() {
  local var="$1" message="$2"
  local value
  read -r -s -p "${message}: " value
  echo
  printf -v "${var}" '%s' "${value}"
}

rand() {
  # openssl rand -hex 24
  openssl rand -hex 24
}

echo "=== infra-core NAS bootstrap ==="

# Default domain for the prompt only. Not written to git.
prompt DOMAIN "Domain" "home.lan"
prompt CATALOG_REPO "GitHub catalog owner/repo (public)"
prompt TZ "Timezone" "Etc/UTC"
prompt PUID "PUID" "1000"
prompt PGID "PGID" "1000"

# ip -4 route get 1.1.1.1 | awk '{print $7; exit}'
DETECTED_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || true)
prompt NAS_LAN_IP "NAS LAN IP" "${DETECTED_IP}"
prompt HTPC_UPSTREAM "HTPC LAN IP (Docker Desktop published ports)"

# ls -d /srv/dev-disk-by-uuid-* 2>/dev/null | head -1
DETECTED_ROOT=$(ls -d /srv/dev-disk-by-uuid-* 2>/dev/null | head -1 || true)
prompt DATA_ROOT "DATA_ROOT (OMV uuid mount)" "${DETECTED_ROOT}"

prompt KOMODO_ADMIN_USER "Komodo admin username" "admin"
prompt_secret KOMODO_ADMIN_PASSWORD "Komodo admin password"
prompt_secret VAULTWARDEN_ADMIN_TOKEN "Vaultwarden admin token"
prompt SIGNUPS_ALLOWED "Vaultwarden SIGNUPS_ALLOWED" "true"
prompt_secret AUTHELIA_USER_PASSWORD "Authelia file-backend password for user 'admin'"
prompt_secret RESTIC_PASSWORD "Restic repo password"
prompt RESTIC_REST_USER "Restic REST username" "restic"
prompt_secret RESTIC_REST_PASSWORD "Restic REST password"
prompt WG_HOST "WireGuard endpoint host (clients dial this)"
prompt_secret GRAFANA_ADMIN_PASSWORD "Grafana admin password"
prompt NEXTCLOUD_ADMIN_USER "Nextcloud admin user" "admin"
prompt_secret NEXTCLOUD_ADMIN_PASSWORD "Nextcloud admin password"

mkdir -p "${KOMODO_DIR}/backups" "${KOMODO_DIR}/bootstrap"
# mkdir -p /etc/komodo/backups /etc/komodo/bootstrap

# --- OMV (may reboot; re-run this script afterwards) ---
if [[ ! -f /usr/bin/omv-confdbadm ]] && [[ ! -f "${KOMODO_DIR}/.omv-installed" ]]; then
  echo "Installing OpenMediaVault (the vendor script may reboot)."
  # wget -O - https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install | bash
  wget -O - https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install | bash
  touch "${KOMODO_DIR}/.omv-installed"
  echo "If the Pi rebooted, log in and run this script again."
fi

# Move OMV workbench off :80 so Caddy can bind 80/443.
# omv-env set OMV_NGINX_SITE_WEBGUI_LISTEN_PORT 81
# omv-salt deploy run nginx
if command -v omv-env >/dev/null 2>&1; then
  omv-env set OMV_NGINX_SITE_WEBGUI_LISTEN_PORT 81 || true
  omv-salt deploy run nginx || true
fi

# --- Docker ---
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker."
  # curl -fsSL https://get.docker.com | sh
  curl -fsSL https://get.docker.com | sh
  # systemctl enable --now docker
  systemctl enable --now docker
fi

# --- DATA_ROOT tree ---
# mkdir -p "${DATA_ROOT}/system" "${DATA_ROOT}/shared/media" ...
mkdir -p \
  "${DATA_ROOT}/system/authelia" \
  "${DATA_ROOT}/system/vaultwarden" \
  "${DATA_ROOT}/system/caddy" \
  "${DATA_ROOT}/system/pihole" \
  "${DATA_ROOT}/system/wireguard" \
  "${DATA_ROOT}/system/homepage" \
  "${DATA_ROOT}/system/restic" \
  "${DATA_ROOT}/system/jellyfin" \
  "${DATA_ROOT}/system/qbittorrent" \
  "${DATA_ROOT}/system/sonarr" \
  "${DATA_ROOT}/system/radarr" \
  "${DATA_ROOT}/system/prowlarr" \
  "${DATA_ROOT}/system/nextcloud" \
  "${DATA_ROOT}/system/homeassistant" \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/users"
# mkdir -p "${DATA_ROOT}/users/<user>/{files,photos}" as you add household users.

# --- Komodo compose.env and core.config.toml ---
DB_PASS=$(rand)
WEBHOOK_SECRET=$(rand)
JWT_SECRET=$(rand)
AUTHELIA_JWT=$(rand)
AUTHELIA_SESSION=$(rand)
AUTHELIA_STORAGE=$(rand)

# openssl rand -hex 24   (used above)

if [[ -d "${REPO_BOOTSTRAP}/komodo" ]]; then
  KOMODO_SRC="${REPO_BOOTSTRAP}/komodo"
elif [[ -d "${SCRIPT_DIR}/komodo" ]]; then
  KOMODO_SRC="${SCRIPT_DIR}/komodo"
else
  echo "Place bootstrap/komodo next to this script (clone infra-core or copy the folder)."
  exit 1
fi

cp "${KOMODO_SRC}/compose.yaml" "${KOMODO_DIR}/bootstrap/compose.yaml"
# cp bootstrap/komodo/compose.yaml /etc/komodo/bootstrap/compose.yaml

cat > "${KOMODO_DIR}/bootstrap/compose.env" <<EOF
COMPOSE_KOMODO_IMAGE_TAG=2
COMPOSE_KOMODO_BACKUPS_PATH=${KOMODO_DIR}/backups
PERIPHERY_ROOT_DIRECTORY=${KOMODO_DIR}
KOMODO_CORE_CONFIG_TOML=${KOMODO_DIR}/core.config.toml
KOMODO_DATABASE_USERNAME=komodo
KOMODO_DATABASE_PASSWORD=${DB_PASS}
TZ=${TZ}
KOMODO_HOST=http://${NAS_LAN_IP}:9120
KOMODO_TITLE=Komodo
KOMODO_LOCAL_AUTH=true
KOMODO_INIT_ADMIN_USERNAME=${KOMODO_ADMIN_USER}
KOMODO_INIT_ADMIN_PASSWORD=${KOMODO_ADMIN_PASSWORD}
KOMODO_FIRST_SERVER_NAME=nas
KOMODO_DISABLE_USER_REGISTRATION=true
KOMODO_ENABLE_NEW_USERS=false
KOMODO_WEBHOOK_SECRET=${WEBHOOK_SECRET}
KOMODO_JWT_SECRET=${JWT_SECRET}
KOMODO_RESOURCE_POLL_INTERVAL=15-min
PERIPHERY_CORE_ADDRESS=ws://core:9120
PERIPHERY_CONNECT_AS=nas
PERIPHERY_CORE_PUBLIC_KEYS=file:/config/keys/core.pub
PERIPHERY_ROOT_DIRECTORY=${KOMODO_DIR}
EOF
# cat > /etc/komodo/bootstrap/compose.env <<'EOF'
# ...generated values; not stored in git...
# EOF

cat > "${KOMODO_DIR}/core.config.toml" <<EOF
title = "Komodo"
[secrets]
CATALOG_REPO = "${CATALOG_REPO}"
DOMAIN = "${DOMAIN}"
TZ = "${TZ}"
NAS_LAN_IP = "${NAS_LAN_IP}"
HTPC_UPSTREAM = "${HTPC_UPSTREAM}"
DATA_ROOT = "${DATA_ROOT}"
PUID = "${PUID}"
PGID = "${PGID}"
VAULTWARDEN_ADMIN_TOKEN = "${VAULTWARDEN_ADMIN_TOKEN}"
SIGNUPS_ALLOWED = "${SIGNUPS_ALLOWED}"
AUTHELIA_JWT_SECRET = "${AUTHELIA_JWT}"
AUTHELIA_SESSION_SECRET = "${AUTHELIA_SESSION}"
AUTHELIA_STORAGE_ENCRYPTION_KEY = "${AUTHELIA_STORAGE}"
RESTIC_PASSWORD = "${RESTIC_PASSWORD}"
RESTIC_REST_USER = "${RESTIC_REST_USER}"
RESTIC_REST_PASSWORD = "${RESTIC_REST_PASSWORD}"
WG_HOST = "${WG_HOST}"
GRAFANA_ADMIN_PASSWORD = "${GRAFANA_ADMIN_PASSWORD}"
NEXTCLOUD_ADMIN_USER = "${NEXTCLOUD_ADMIN_USER}"
NEXTCLOUD_ADMIN_PASSWORD = "${NEXTCLOUD_ADMIN_PASSWORD}"
EOF
chmod 600 "${KOMODO_DIR}/core.config.toml" "${KOMODO_DIR}/bootstrap/compose.env"
# chmod 600 /etc/komodo/core.config.toml /etc/komodo/bootstrap/compose.env

# --- edge network ---
# docker network create edge
docker network create edge 2>/dev/null || true

# --- Core + local Periphery ---
# docker compose --env-file /etc/komodo/bootstrap/compose.env -f /etc/komodo/bootstrap/compose.yaml up -d
docker compose --env-file "${KOMODO_DIR}/bootstrap/compose.env" \
  -f "${KOMODO_DIR}/bootstrap/compose.yaml" up -d

echo "Waiting for Komodo Core on :9120..."
for _ in $(seq 1 60); do
  # curl -sf http://127.0.0.1:9120/ >/dev/null
  if curl -sf "http://127.0.0.1:9120/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# --- Authelia users file (hash via official image) ---
# docker run --rm ghcr.io/authelia/authelia:latest authelia crypto hash generate argon2 --password '...'
HASH=$(docker run --rm ghcr.io/authelia/authelia:latest \
  authelia crypto hash generate argon2 --password "${AUTHELIA_USER_PASSWORD}" \
  | awk '/Password hash:/ {print $3}')
cat > "${DATA_ROOT}/system/authelia/users.yml" <<EOF
users:
  admin:
    displayname: admin
    password: "${HASH}"
    email: admin@${DOMAIN}
    groups:
      - admins
      - dev
EOF
chmod 600 "${DATA_ROOT}/system/authelia/users.yml"
# chmod 600 "\${DATA_ROOT}/system/authelia/users.yml"

# --- wg-easy password hash (best-effort; can set WG_PASSWORD_HASH later in Komodo) ---
# docker run --rm ghcr.io/wg-easy/wg-easy:15 wgpw '...'   # image-specific
echo "Set Komodo secret WG_PASSWORD_HASH (wg-easy hash) before deploying WireGuard."

echo
echo "Komodo Core should be at http://${NAS_LAN_IP}:9120"
echo "Log in as ${KOMODO_ADMIN_USER}."
echo "Server 'nas' is KOMODO_FIRST_SERVER_NAME / PERIPHERY_CONNECT_AS."
echo
echo "Create a ResourceSync (webhooks disabled):"
echo "  repo:            ${CATALOG_REPO}"
echo "  branch:          main"
echo "  resource path:   stacks/komodo"
echo "  poll:            enabled"
echo "  webhook_enabled: false"
echo
echo "Komodo [secrets] were written to ${KOMODO_DIR}/core.config.toml"
echo "Also add remaining keys from stacks/komodo/VARIABLES.md (widget tokens, BACKUP_DRIVE on htpc)."
echo
echo "Done."
