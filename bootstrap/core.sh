#!/usr/bin/env bash
# Core host Layer 0 bootstrap. Copy to the Core machine (scp) and run as root.
# Every live command is also shown in a nearby comment for copy-paste.
#
# Order: apt → external disk? → (if yes: OMV, may reboot, mount uuid path)
#        (if no: directory on OS disk) → site prompts → Docker → Komodo.

set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

KOMODO_DIR=/etc/komodo
ANSWERS="${KOMODO_DIR}/bootstrap-answers.env"
STATE="${KOMODO_DIR}/bootstrap-state.env"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_BOOTSTRAP="${SCRIPT_DIR}"
# If you copied only this script, set REPO_BOOTSTRAP to a clone of infra-core/bootstrap.

mkdir -p "${KOMODO_DIR}/backups" "${KOMODO_DIR}/bootstrap"
# mkdir -p /etc/komodo/backups /etc/komodo/bootstrap

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

quote_s() {
  printf "%s" "$1" | sed "s/'/'\\\\''/g"
}

save_answers() {
  local old
  old=$(umask)
  umask 077
  cat > "${ANSWERS}" <<EOF
DOMAIN='$(quote_s "${DOMAIN}")'
CATALOG_REPO='$(quote_s "${CATALOG_REPO}")'
TZ='$(quote_s "${TZ}")'
PUID='$(quote_s "${PUID}")'
PGID='$(quote_s "${PGID}")'
CORE_SERVER='$(quote_s "${CORE_SERVER}")'
PERIPHERY_SERVER='$(quote_s "${PERIPHERY_SERVER}")'
NAS_LAN_IP='$(quote_s "${NAS_LAN_IP}")'
HTPC_UPSTREAM='$(quote_s "${HTPC_UPSTREAM}")'
KOMODO_ADMIN_USER='$(quote_s "${KOMODO_ADMIN_USER}")'
KOMODO_ADMIN_PASSWORD='$(quote_s "${KOMODO_ADMIN_PASSWORD}")'
VAULTWARDEN_ADMIN_TOKEN='$(quote_s "${VAULTWARDEN_ADMIN_TOKEN}")'
SIGNUPS_ALLOWED='$(quote_s "${SIGNUPS_ALLOWED}")'
AUTHELIA_USER_PASSWORD='$(quote_s "${AUTHELIA_USER_PASSWORD}")'
RESTIC_PASSWORD='$(quote_s "${RESTIC_PASSWORD}")'
RESTIC_REST_USER='$(quote_s "${RESTIC_REST_USER}")'
RESTIC_REST_PASSWORD='$(quote_s "${RESTIC_REST_PASSWORD}")'
WG_HOST='$(quote_s "${WG_HOST}")'
GRAFANA_ADMIN_PASSWORD='$(quote_s "${GRAFANA_ADMIN_PASSWORD}")'
NEXTCLOUD_ADMIN_USER='$(quote_s "${NEXTCLOUD_ADMIN_USER}")'
NEXTCLOUD_ADMIN_PASSWORD='$(quote_s "${NEXTCLOUD_ADMIN_PASSWORD}")'
DATA_ROOT='$(quote_s "${DATA_ROOT:-}")'
EOF
  umask "${old}"
}

save_state() {
  local old
  old=$(umask)
  umask 077
  cat > "${STATE}" <<EOF
USE_EXTERNAL_DISK='$(quote_s "${USE_EXTERNAL_DISK:-}")'
DATA_ROOT='$(quote_s "${DATA_ROOT:-}")'
EOF
  umask "${old}"
}

root_disk() {
  local src pk
  src=$(findmnt -n -o SOURCE /)
  pk=$(lsblk -ndo PKNAME "${src}" 2>/dev/null || true)
  if [[ -n "${pk}" ]]; then
    echo "${pk}"
  else
    echo "${src#/dev/}" | sed 's/p\?[0-9]\+$//'
  fi
}

part_from_disk() {
  local d="$1"
  local base="${d#/dev/}"
  if [[ "${base}" == mmcblk* || "${base}" == nvme* || "${base}" == loop* ]]; then
    echo "/dev/${base}p1"
  else
    echo "/dev/${base}1"
  fi
}

ensure_data_disk() {
  local existing os_disk default_disk disk confirm fstype uuid part mountpt
  existing=$(ls -d /srv/dev-disk-by-uuid-* 2>/dev/null | head -1 || true)
  if [[ -n "${existing}" ]] && findmnt -n "${existing}" >/dev/null 2>&1; then
    DATA_ROOT="${existing}"
    echo "Using existing OMV data mount: ${DATA_ROOT}"
    return
  fi

  # apt-get install -y parted util-linux e2fsprogs
  apt-get install -y parted util-linux e2fsprogs

  os_disk=$(root_disk)
  echo
  echo "Block devices (OS disk ${os_disk} will not be used as DATA_ROOT):"
  # lsblk -dn -o NAME,SIZE,MODEL,TRAN,TYPE
  lsblk -dn -o NAME,SIZE,MODEL,TRAN,TYPE | awk '$NF=="disk" {print}'
  echo

  default_disk=""
  while read -r name; do
    [[ "${name}" == "${os_disk}" ]] && continue
    default_disk="/dev/${name}"
    break
  done < <(lsblk -dn -o NAME,TYPE | awk '$2=="disk" {print $1}')

  if [[ -z "${default_disk}" ]]; then
    echo "No extra disk found. Plug in the USB data drive (or SATA disk) and re-run."
    exit 1
  fi

  prompt disk "Data disk to use for DATA_ROOT (mounted at /srv/dev-disk-by-uuid-<UUID>)" "${default_disk}"
  disk="${disk#/dev/}"
  disk="/dev/${disk#/dev/}"
  if [[ ! -b "${disk}" ]]; then
    echo "Not a block device: ${disk}"
    exit 1
  fi
  if [[ "${disk#/dev/}" == "${os_disk}" ]]; then
    echo "Refusing to use the OS disk as DATA_ROOT."
    exit 1
  fi

  part=$(lsblk -ln -o NAME,TYPE "${disk}" | awk '$2=="part" {print "/dev/"$1; exit}')
  if [[ -n "${part}" ]]; then
    fstype=$(blkid -s TYPE -o value "${part}" 2>/dev/null || true)
    uuid=$(blkid -s UUID -o value "${part}" 2>/dev/null || true)
  else
    fstype=""
    uuid=""
    part=$(part_from_disk "${disk}")
  fi

  if [[ "${fstype}" != "ext4" || -z "${uuid}" ]]; then
    echo "No ext4 filesystem on ${disk}."
    prompt confirm "Type YES to partition and format ${disk} (ERASES ALL DATA on it)" ""
    if [[ "${confirm}" != "YES" ]]; then
      echo "Aborted. Format the disk in OMV or re-run and type YES."
      exit 1
    fi
    # wipefs -a /dev/sdX
    wipefs -a "${disk}" || true
    # parted -s /dev/sdX mklabel gpt
    # parted -s /dev/sdX mkpart primary ext4 0% 100%
    parted -s "${disk}" mklabel gpt
    parted -s "${disk}" mkpart primary ext4 0% 100%
    partprobe "${disk}" || true
    sleep 2
    part=$(part_from_disk "${disk}")
    if [[ ! -b "${part}" ]]; then
      part=$(lsblk -ln -o NAME,TYPE "${disk}" | awk '$2=="part" {print "/dev/"$1; exit}')
    fi
    # mkfs.ext4 -F -L core-data /dev/sdX1
    mkfs.ext4 -F -L core-data "${part}"
    uuid=$(blkid -s UUID -o value "${part}")
  fi

  mountpt="/srv/dev-disk-by-uuid-${uuid}"
  # mkdir -p /srv/dev-disk-by-uuid-<UUID>
  mkdir -p "${mountpt}"
  if ! grep -q "${uuid}" /etc/fstab; then
    # echo "UUID=<uuid> /srv/dev-disk-by-uuid-<uuid> ext4 defaults,nofail 0 2" >> /etc/fstab
    echo "UUID=${uuid} ${mountpt} ext4 defaults,nofail 0 2" >> /etc/fstab
  fi
  # mount /srv/dev-disk-by-uuid-<UUID>
  mount "${mountpt}" 2>/dev/null || mount "UUID=${uuid}" "${mountpt}"

  if command -v omv-rpc >/dev/null 2>&1; then
    # omv-rpc FileSystemMgmt mount '{"id":"<uuid>","fstab":true}'
    omv-rpc FileSystemMgmt mount "{\"id\":\"${uuid}\",\"fstab\":true}" >/dev/null 2>&1 || true
  fi

  DATA_ROOT="${mountpt}"
  echo "DATA_ROOT=${DATA_ROOT}"
}

# Debian trixie apt verifies with sqv as user _apt. A 0600 keyring (common if
# umask was 077 when gpg --dearmor wrote it) makes the OMV repo look unsigned.
repair_apt_keyrings() {
  local kr=/usr/share/keyrings/openmediavault-archive-keyring.gpg
  local f
  # chmod 755 /usr/share/keyrings
  [[ -d /usr/share/keyrings ]] && chmod 755 /usr/share/keyrings
  [[ -d /etc/apt/keyrings ]] && chmod 755 /etc/apt/keyrings
  if [[ -f "${kr}" ]]; then
    # chmod 644 /usr/share/keyrings/openmediavault-archive-keyring.gpg
    chmod 644 "${kr}"
    chown root:root "${kr}"
  fi
  shopt -s nullglob
  for f in /usr/share/keyrings/*.gpg /usr/share/keyrings/*.asc \
           /etc/apt/keyrings/*.gpg /etc/apt/keyrings/*.asc \
           /etc/apt/trusted.gpg.d/*; do
    [[ -f "${f}" ]] || continue
    chmod a+r "${f}" || true
  done
  shopt -u nullglob
}

seed_omv_keyring() {
  local kr=/usr/share/keyrings/openmediavault-archive-keyring.gpg
  local tmp
  repair_apt_keyrings
  if [[ -s "${kr}" ]]; then
    return
  fi
  # apt-get install -y gnupg
  command -v gpg >/dev/null 2>&1 || apt-get install -y gnupg
  tmp=$(mktemp)
  # wget --quiet -O - https://packages.openmediavault.io/archive.key | gpg --dearmor --yes --output /usr/share/keyrings/openmediavault-archive-keyring.gpg
  wget --quiet -O - https://packages.openmediavault.io/archive.key \
    | gpg --dearmor --yes --output "${tmp}"
  install -m 644 -o root -g root "${tmp}" "${kr}"
  rm -f "${tmp}"
}

install_omv() {
  local installer="https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install"
  seed_omv_keyring
  echo "Installing OpenMediaVault (the vendor script may reboot)."
  echo "If it reboots, run this script again; it will continue with disk mount, then prompts."
  # gpg --dearmor inherits umask; 022 so the vendor script writes a readable keyring.
  umask 022
  # wget -O - https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install | bash
  if ! wget -O - "${installer}" | bash; then
    echo "OMV installer failed (often an unreadable apt keyring on Debian/sqv). Fixing permissions and retrying."
    repair_apt_keyrings
    # apt-get update
    apt-get update
    wget -O - "${installer}" | bash
  fi
  repair_apt_keyrings
  echo "If the host rebooted, log in and run this script again."
}

echo "=== infra-core Core bootstrap ==="

# --- Refresh OS packages (do this first on a fresh OS image) ---
# apt-get update
# DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
export DEBIAN_FRONTEND=noninteractive
repair_apt_keyrings
if ! apt-get update; then
  echo "apt-get update failed; repairing apt keyring permissions and retrying."
  repair_apt_keyrings
  apt-get update
fi
apt-get upgrade -y

USE_EXTERNAL_DISK=""
DATA_ROOT=""
if [[ -f "${STATE}" ]]; then
  # shellcheck disable=SC1090
  source "${STATE}"
  echo "Loaded storage state from ${STATE} (OMV reboot / re-run)."
fi

if [[ -z "${USE_EXTERNAL_DISK}" ]]; then
  prompt ext "Use an external disk for DATA_ROOT? (y/n)" "y"
  case "${ext}" in
    y|Y|yes|YES) USE_EXTERNAL_DISK=yes ;;
    *) USE_EXTERNAL_DISK=no ;;
  esac
  save_state
fi

if [[ "${USE_EXTERNAL_DISK}" == "yes" ]]; then
  # --- OMV (may reboot; re-run this script — storage choice is saved in STATE) ---
  if [[ ! -x /usr/sbin/omv-confdbadm ]] && [[ ! -x /usr/bin/omv-confdbadm ]]; then
    install_omv
  fi

  # Move OMV workbench off :80 so Caddy can bind 80/443.
  # omv-env set OMV_NGINX_SITE_WEBGUI_LISTEN_PORT 81
  # omv-salt deploy run nginx
  if command -v omv-env >/dev/null 2>&1; then
    omv-env set OMV_NGINX_SITE_WEBGUI_LISTEN_PORT 81 || true
    omv-salt deploy run nginx || true
  fi

  if [[ -z "${DATA_ROOT}" || ! -d "${DATA_ROOT}" ]]; then
    ensure_data_disk
    save_state
  else
    echo "Using DATA_ROOT=${DATA_ROOT}"
  fi
else
  if [[ -z "${DATA_ROOT}" ]]; then
    prompt DATA_ROOT "Directory on the OS disk for DATA_ROOT" "/srv/core"
  fi
  # mkdir -p /srv/core
  mkdir -p "${DATA_ROOT}"
  save_state
fi

# --- Site prompts (after storage is ready, including any OMV reboot) ---
if [[ -f "${ANSWERS}" ]]; then
  # shellcheck disable=SC1090
  source "${ANSWERS}"
  echo "Loaded saved site answers from ${ANSWERS}."
else
  # Default domain for the prompt only. Not written to git.
  prompt DOMAIN "Domain" "home.lan"
  prompt CATALOG_REPO "GitHub catalog owner/repo (public)"
  prompt TZ "Timezone" "America/Los_Angeles"
  prompt PUID "PUID" "1000"
  prompt PGID "PGID" "1000"
  prompt CORE_SERVER "Komodo server name for this host (Core + local Periphery)" "core"
  prompt PERIPHERY_SERVER "Komodo server name for the remote Periphery host" "periphery"

  # ip -4 route get 1.1.1.1 | awk '{print $7; exit}'
  DETECTED_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || true)
  prompt NAS_LAN_IP "LAN IP of this host (Core)" "${DETECTED_IP}"
  prompt HTPC_UPSTREAM "LAN IP of the remote Periphery host (published Docker ports)"

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
  save_answers
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
if [[ -f "${KOMODO_DIR}/bootstrap/compose.env" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${KOMODO_DIR}/bootstrap/compose.env"
  set +a
  DB_PASS="${KOMODO_DATABASE_PASSWORD}"
  WEBHOOK_SECRET="${KOMODO_WEBHOOK_SECRET}"
  JWT_SECRET="${KOMODO_JWT_SECRET}"
else
  DB_PASS=$(rand)
  WEBHOOK_SECRET=$(rand)
  JWT_SECRET=$(rand)
fi
if [[ -f "${KOMODO_DIR}/core.config.toml" ]] && grep -q AUTHELIA_JWT_SECRET "${KOMODO_DIR}/core.config.toml"; then
  AUTHELIA_JWT=$(awk -F '"' '/AUTHELIA_JWT_SECRET/ {print $2}' "${KOMODO_DIR}/core.config.toml")
  AUTHELIA_SESSION=$(awk -F '"' '/AUTHELIA_SESSION_SECRET/ {print $2}' "${KOMODO_DIR}/core.config.toml")
  AUTHELIA_STORAGE=$(awk -F '"' '/AUTHELIA_STORAGE_ENCRYPTION_KEY/ {print $2}' "${KOMODO_DIR}/core.config.toml")
else
  AUTHELIA_JWT=$(rand)
  AUTHELIA_SESSION=$(rand)
  AUTHELIA_STORAGE=$(rand)
fi

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
KOMODO_FIRST_SERVER_NAME=${CORE_SERVER}
KOMODO_PERIPHERY_PUBLIC_KEY=file:/config/keys/periphery.pub
KOMODO_DISABLE_USER_REGISTRATION=true
KOMODO_ENABLE_NEW_USERS=false
KOMODO_WEBHOOK_SECRET=${WEBHOOK_SECRET}
KOMODO_JWT_SECRET=${JWT_SECRET}
KOMODO_RESOURCE_POLL_INTERVAL=15-min
PERIPHERY_CORE_ADDRESS=ws://core:9120
PERIPHERY_CONNECT_AS=${CORE_SERVER}
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
CORE_SERVER = "${CORE_SERVER}"
PERIPHERY_SERVER = "${PERIPHERY_SERVER}"
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
chmod 600 "${KOMODO_DIR}/core.config.toml" "${KOMODO_DIR}/bootstrap/compose.env" "${ANSWERS}"
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
if [[ ! -f "${DATA_ROOT}/system/authelia/users.yml" ]]; then
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
fi
# chmod 600 "\${DATA_ROOT}/system/authelia/users.yml"

# --- wg-easy password hash (best-effort; can set WG_PASSWORD_HASH later in Komodo) ---
# docker run --rm ghcr.io/wg-easy/wg-easy:15 wgpw '...'   # image-specific
echo "Set Komodo secret WG_PASSWORD_HASH (wg-easy hash) before deploying WireGuard."

echo
echo "DATA_ROOT=${DATA_ROOT}"
echo "Komodo Core should be at http://${NAS_LAN_IP}:9120"
echo "Log in as ${KOMODO_ADMIN_USER}."
echo "Server '${CORE_SERVER}' is KOMODO_FIRST_SERVER_NAME / PERIPHERY_CONNECT_AS."
echo "Remote Periphery should connect_as '${PERIPHERY_SERVER}'."
echo
echo "Create a ResourceSync (webhooks disabled):"
echo "  repo:            ${CATALOG_REPO}"
echo "  branch:          main"
echo "  resource path:   stacks/komodo"
echo "  poll:            enabled"
echo "  webhook_enabled: false"
echo
echo "Komodo [secrets] were written to ${KOMODO_DIR}/core.config.toml"
echo "Also add remaining keys from stacks/komodo/VARIABLES.md (widget tokens, BACKUP_DRIVE on the remote host)."
echo
echo "Done."
