#!/usr/bin/env bash
# Core host Layer 0 bootstrap. Copy the bootstrap/ directory to the Core machine
# (core.sh, omv-nfs.sh, data-root-perms.sh, komodo/) and run as root:
#   sudo bash core.sh
# Every live command is also shown in a nearby comment for copy-paste.
#
# Order: apt → external disk? → (if yes: OMV with -n -r, mount uuid path)
#        (if no: directory on OS disk) → site prompts → Docker → DATA_ROOT tree
#        (system/<app>, not system/core) → Komodo → NFS shared/+users/ → ACLs.

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
OPENCLOUD_ADMIN_PASSWORD='$(quote_s "${OPENCLOUD_ADMIN_PASSWORD}")'
IMMICH_DB_PASSWORD='$(quote_s "${IMMICH_DB_PASSWORD}")'
LINKDING_SUPERUSER_NAME='$(quote_s "${LINKDING_SUPERUSER_NAME:-admin}")'
LINKDING_SUPERUSER_PASSWORD='$(quote_s "${LINKDING_SUPERUSER_PASSWORD}")'
ADVENTURELOG_POSTGRES_PASSWORD='$(quote_s "${ADVENTURELOG_POSTGRES_PASSWORD}")'
ADVENTURELOG_ADMIN_PASSWORD='$(quote_s "${ADVENTURELOG_ADMIN_PASSWORD}")'
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

# Register DATA_ROOT with OMV (config.xml + tagged fstab) so Shared Folders/SMB/NFS work.
# Do not write a plain UUID fstab line first: OMV hides already-mounted disks from
# the Mount UI, and Salt will not fill the [openmediavault] block.
register_omv_filesystem() {
  local uuid="$1"
  local mountpt="/srv/dev-disk-by-uuid-${uuid}"
  local out rc=0
  mkdir -p "${mountpt}"
  if ! command -v omv-rpc >/dev/null 2>&1; then
    return 1
  fi
  # omv-rpc -u admin FileSystemMgmt setMountPoint '{"id":"<uuid>","usagewarnthreshold":85}'
  out=$(omv-rpc -u admin FileSystemMgmt setMountPoint \
    "{\"id\":\"${uuid}\",\"usagewarnthreshold\":85}" 2>&1) || rc=$?
  if [[ "${rc}" -ne 0 ]] && ! grep -qi 'already exists' <<<"${out}"; then
    echo "OMV setMountPoint failed: ${out}"
    return 1
  fi
  echo "OMV filesystem object exists for ${uuid}."
  # Drop an untagged bootstrap fstab line so Salt can write the tagged one.
  if grep -q "^UUID=${uuid} " /etc/fstab; then
    awk -v u="UUID=${uuid} " '
      BEGIN { inblk = 0 }
      /# >>> \[openmediavault\]/ { inblk = 1 }
      inblk == 0 && index($0, u) == 1 { next }
      { print }
      /# <<< \[openmediavault\]/ { inblk = 0 }
    ' /etc/fstab > /etc/fstab.omvnew
    mv /etc/fstab.omvnew /etc/fstab
  fi
  # omv-salt deploy run fstab
  omv-salt deploy run fstab
  findmnt -n "${mountpt}" >/dev/null 2>&1
}

ensure_data_disk() {
  local existing os_disk default_disk disk confirm fstype uuid part mountpt
  existing=$(ls -d /srv/dev-disk-by-uuid-* 2>/dev/null | head -1 || true)
  if [[ -n "${existing}" ]] && findmnt -n "${existing}" >/dev/null 2>&1; then
    DATA_ROOT="${existing}"
    echo "Using existing OMV data mount: ${DATA_ROOT}"
    uuid="${existing#/srv/dev-disk-by-uuid-}"
    register_omv_filesystem "${uuid}" || true
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
  if ! register_omv_filesystem "${uuid}"; then
    echo "OMV did not take the disk; falling back to a plain fstab mount."
    # echo "UUID=<uuid> /srv/dev-disk-by-uuid-<uuid> ext4 defaults,nofail 0 2" >> /etc/fstab
    if ! grep -q "${uuid}" /etc/fstab; then
      echo "UUID=${uuid} ${mountpt} ext4 defaults,nofail 0 2" >> /etc/fstab
    fi
    # mount /srv/dev-disk-by-uuid-<UUID>
    mount "${mountpt}" 2>/dev/null || mount "UUID=${uuid}" "${mountpt}"
  fi
  if ! findmnt -n "${mountpt}" >/dev/null 2>&1; then
    echo "Failed to mount DATA_ROOT at ${mountpt}."
    exit 1
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

# OMV workbench listen port is conf.webadmin.port in the OMV database, not
# OMV_NGINX_SITE_WEBGUI_LISTEN_PORT (that env var does not change nginx).
move_omv_workbench_off_http() {
  local omv_confdbadm
  omv_confdbadm=$(command -v omv-confdbadm || true)
  if [[ -x /usr/sbin/omv-confdbadm ]]; then
    omv_confdbadm=/usr/sbin/omv-confdbadm
  fi
  if [[ -z "${omv_confdbadm}" ]]; then
    return 0
  fi

  echo "Moving OMV workbench to :81 and disabling OMV TLS so Caddy can bind :80/:443."
  # omv-confdbadm read conf.webadmin
  # python3 -c '...'  # set port=81, enablessl=false
  # omv-confdbadm update conf.webadmin '{...}'
  python3 - "${omv_confdbadm}" <<'PY'
import json, subprocess, sys
tool = sys.argv[1]
cfg = json.loads(subprocess.check_output([tool, "read", "conf.webadmin"], text=True))
cfg["port"] = 81
cfg["enablessl"] = False
cfg["forcesslonly"] = False
subprocess.check_call([tool, "update", "conf.webadmin", json.dumps(cfg)])
print(json.dumps(cfg))
PY
  # omv-salt deploy run nginx
  omv-salt deploy run nginx

  if command -v docker >/dev/null 2>&1 && docker inspect caddy >/dev/null 2>&1; then
    # docker start caddy
    docker start caddy >/dev/null 2>&1 || docker restart caddy >/dev/null 2>&1 || true
  fi

  echo "Host listeners after OMV move:"
  # ss -tlnp | grep -E ':80|:443|:81|:9120'
  ss -tlnp | grep -E ':80|:443|:81|:9120' || true
}

run_omv_installer() {
  local installer_url="$1"
  local tmp
  tmp=$(mktemp)
  # wget -O /tmp/omv-install https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install
  # bash /tmp/omv-install -n -r
  wget -O "${tmp}" "${installer_url}"
  if [[ ! -s "${tmp}" ]]; then
    echo "Failed to download OMV installer from ${installer_url}"
    rm -f "${tmp}"
    return 1
  fi
  # -n skip network setup (do not purge NetworkManager / rewrite systemd-networkd)
  # -r skip reboot
  echo "Running vendor OMV installer with -n -r (keep DHCP/SSH, no reboot)."
  if bash "${tmp}" -n -r; then
    rm -f "${tmp}"
    return 0
  fi
  rm -f "${tmp}"
  return 1
}

assert_ipv4_route() {
  if ip -4 route get 1.1.1.1 >/dev/null 2>&1; then
    echo "IPv4 default route still present after OMV install."
    # ip -4 addr show scope global
    ip -4 addr show scope global || true
    return 0
  fi
  echo "ERROR: no IPv4 default route after OMV install. SSH may die; aborting."
  ip -br addr || true
  return 1
}

install_omv() {
  local installer="https://github.com/OpenMediaVault-Plugin-Developers/installScript/raw/master/install"
  seed_omv_keyring
  echo "Installing OpenMediaVault without taking over the NIC."
  # gpg --dearmor inherits umask; 022 so the vendor script writes a readable keyring.
  umask 022
  if ! run_omv_installer "${installer}"; then
    echo "OMV installer failed (often an unreadable apt keyring on Debian/sqv). Fixing permissions and retrying."
    repair_apt_keyrings
    # apt-get update
    apt-get update
    run_omv_installer "${installer}"
  fi
  repair_apt_keyrings
  assert_ipv4_route
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
  # --- OMV (installer is -n -r: keep NIC, do not reboot) ---
  if [[ ! -x /usr/sbin/omv-confdbadm ]] && [[ ! -x /usr/bin/omv-confdbadm ]]; then
    install_omv
  fi

  # Move OMV workbench off :80 so Caddy can bind 80/443.
  move_omv_workbench_off_http

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
  if [[ -z "${OPENCLOUD_ADMIN_PASSWORD:-}" ]]; then
    OPENCLOUD_ADMIN_PASSWORD=$(rand)
    echo "Generated OPENCLOUD_ADMIN_PASSWORD (save now; add in Komodo if Core is already running)."
    save_answers
  fi
  if [[ -z "${IMMICH_DB_PASSWORD:-}" ]]; then
    IMMICH_DB_PASSWORD=$(rand)
    echo "Generated IMMICH_DB_PASSWORD (save now; add in Komodo if Core is already running)."
    save_answers
  fi
  if [[ -z "${LINKDING_SUPERUSER_NAME:-}" ]]; then
    LINKDING_SUPERUSER_NAME=admin
    save_answers
  fi
  if [[ -z "${LINKDING_SUPERUSER_PASSWORD:-}" ]]; then
    LINKDING_SUPERUSER_PASSWORD=$(rand)
    echo "Generated LINKDING_SUPERUSER_PASSWORD (save now; add in Komodo if Core is already running)."
    save_answers
  fi
  if [[ -z "${ADVENTURELOG_POSTGRES_PASSWORD:-}" ]]; then
    ADVENTURELOG_POSTGRES_PASSWORD=$(rand)
    echo "Generated ADVENTURELOG_POSTGRES_PASSWORD (save now; add in Komodo if Core is already running)."
    save_answers
  fi
  if [[ -z "${ADVENTURELOG_ADMIN_PASSWORD:-}" ]]; then
    ADVENTURELOG_ADMIN_PASSWORD=$(rand)
    echo "Generated ADVENTURELOG_ADMIN_PASSWORD (save now; add in Komodo if Core is already running)."
    save_answers
  fi
else
  # Default domain for the prompt only. Not written to git.
  prompt DOMAIN "Domain" "home.lan"
  prompt CATALOG_REPO "Catalog owner/repo path (Gitea; same name as the GitHub mirror)"
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
  prompt WG_HOST "WireGuard public endpoint host (off-LAN DNS name, not a LAN name)"
  prompt_secret GRAFANA_ADMIN_PASSWORD "Grafana admin password"
  prompt_secret OPENCLOUD_ADMIN_PASSWORD "OpenCloud admin password (user admin)"
  prompt_secret IMMICH_DB_PASSWORD "Immich PostgreSQL password (role immich)"
  prompt LINKDING_SUPERUSER_NAME "Linkding admin username" "admin"
  prompt_secret LINKDING_SUPERUSER_PASSWORD "Linkding admin password"
  prompt_secret ADVENTURELOG_POSTGRES_PASSWORD "Adventure Log PostgreSQL password"
  prompt_secret ADVENTURELOG_ADMIN_PASSWORD "Adventure Log admin password"
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

# Host-network WireGuard NATs on the real NIC. Persist forwarding (Docker
# often sets this already; required if Core starts WG before Docker does).
# echo net.ipv4.ip_forward=1 > /etc/sysctl.d/99-ip-forward.conf
# sysctl -w net.ipv4.ip_forward=1
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-ip-forward.conf
sysctl -w net.ipv4.ip_forward=1

# --- DATA_ROOT tree ---
# Core app state under system/<app>. Periphery /config is local on the HTPC.
mkdir -p \
  "${DATA_ROOT}/system/authelia" \
  "${DATA_ROOT}/system/vaultwarden" \
  "${DATA_ROOT}/system/gitea" \
  "${DATA_ROOT}/system/pihole" \
  "${DATA_ROOT}/system/wireguard" \
  "${DATA_ROOT}/system/restic" \
  "${DATA_ROOT}/system/opencloud/config" \
  "${DATA_ROOT}/system/opencloud/data" \
  "${DATA_ROOT}/system/opencloud/posix" \
  "${DATA_ROOT}/system/jotty/data" \
  "${DATA_ROOT}/system/jotty/config" \
  "${DATA_ROOT}/system/jotty/cache" \
  "${DATA_ROOT}/system/linkding" \
  "${DATA_ROOT}/system/rustdesk" \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/shared/cameras" \
  "${DATA_ROOT}/users"
# mkdir -p "${DATA_ROOT}/users/<user>/{files,photos}" as you add household users.
chown -R "${PUID}:${PGID}" "${DATA_ROOT}/system/opencloud"
chown -R "${PUID}:${PGID}" "${DATA_ROOT}/system/jotty"

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
if [[ -f "${KOMODO_DIR}/core.config.toml" ]] && grep -q '^WG_UI_PASSWORD' "${KOMODO_DIR}/core.config.toml"; then
  WG_UI_PASSWORD=$(awk -F '"' '/^WG_UI_PASSWORD/ {print $2}' "${KOMODO_DIR}/core.config.toml")
else
  WG_UI_PASSWORD=$(rand)
  echo "WireGuard UI user wg-admin password (save now): ${WG_UI_PASSWORD}"
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
KOMODO_HOST=https://ops.${DOMAIN}
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
NFS_EXPORT = "/shared"
NFS_USERS = "/users"
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
WG_UI_PASSWORD = "${WG_UI_PASSWORD}"
GRAFANA_ADMIN_PASSWORD = "${GRAFANA_ADMIN_PASSWORD}"
OPENCLOUD_ADMIN_PASSWORD = "${OPENCLOUD_ADMIN_PASSWORD}"
IMMICH_DB_PASSWORD = "${IMMICH_DB_PASSWORD}"
LINKDING_SUPERUSER_NAME = "${LINKDING_SUPERUSER_NAME}"
LINKDING_SUPERUSER_PASSWORD = "${LINKDING_SUPERUSER_PASSWORD}"
ADVENTURELOG_POSTGRES_PASSWORD = "${ADVENTURELOG_POSTGRES_PASSWORD}"
ADVENTURELOG_ADMIN_PASSWORD = "${ADVENTURELOG_ADMIN_PASSWORD}"
HOMEPAGE_VAR_PIHOLE_TOKEN = ""
HOMEPAGE_VAR_JELLYFIN_KEY = ""
HOMEPAGE_VAR_SONARR_KEY = ""
HOMEPAGE_VAR_RADARR_KEY = ""
HOMEPAGE_VAR_PROWLARR_KEY = ""
HOMEPAGE_VAR_QBIT_USERNAME = ""
HOMEPAGE_VAR_QBIT_PASSWORD = ""
HOMEPAGE_VAR_GRAFANA_KEY = ""
HOMEPAGE_VAR_WGEASY_PASSWORD = ""
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

# --- NFS: shared/ and users/ only (HTPC Docker). Do not export system/. ---
if command -v omv-rpc >/dev/null 2>&1 && [[ -f "${REPO_BOOTSTRAP}/omv-nfs.sh" ]]; then
  echo "Exporting shared/ and users/ over NFS to ${HTPC_UPSTREAM}."
  # sudo HTPC_IP=<HTPC> DATA_ROOT=<DATA_ROOT> bash bootstrap/omv-nfs.sh
  HTPC_IP="${HTPC_UPSTREAM}" DATA_ROOT="${DATA_ROOT}" bash "${REPO_BOOTSTRAP}/omv-nfs.sh"
else
  echo "OMV NFS skipped (no omv-rpc). For HTPC compose.nfs.yaml, follow bootstrap/omv-nfs.md."
fi

# --- POSIX/ACL on DATA_ROOT (system/ is root-only; household SMB on shared/ and users/) ---
if [[ -f "${REPO_BOOTSTRAP}/data-root-perms.sh" ]]; then
  # sudo DATA_ROOT=<DATA_ROOT> bash bootstrap/data-root-perms.sh
  DATA_ROOT="${DATA_ROOT}" bash "${REPO_BOOTSTRAP}/data-root-perms.sh"
fi

# --- Authelia users file (hash via official image) ---
# docker run --rm authelia/authelia:4 authelia crypto hash generate argon2 --password '...'
users_file="${DATA_ROOT}/system/authelia/users.yml"
if [[ -d "${users_file}" ]]; then
  echo "Replacing directory ${users_file} (Docker created it when the file was missing)."
  rm -rf "${users_file}"
fi
if [[ ! -f "${users_file}" ]] || ! grep -q '^    password: '\''\$' "${users_file}"; then
  HASH=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate argon2 --password "${AUTHELIA_USER_PASSWORD}" \
    | awk '/^Digest:/ {print $2}')
  if [[ -z "${HASH}" ]]; then
    HASH="\$plaintext\$${AUTHELIA_USER_PASSWORD}"
  fi
  cat > "${users_file}" <<EOF
users:
  admin:
    disabled: false
    displayname: 'admin'
    password: '${HASH}'
    email: 'admin@${DOMAIN}'
    groups:
      - admins
      - dev
EOF
  chmod 644 "${users_file}"
fi

echo "WireGuard UI is user wg-admin; password is Komodo secret WG_UI_PASSWORD."
echo "After ResourceSync deploys the wireguard stack (host network; Caddy vpn.${DOMAIN} → Core :51821):"
echo "  Router: UDP 51820 only → ${NAS_LAN_IP} (not 51821, not 80/443)."
echo "  WG_HOST must resolve on the public internet to this site's WAN IPv4 (Dynamic DNS if the WAN moves)."
echo "  Do not set DOMAIN to a public zone that would make Pi-hole answer the WG_HOST name as the LAN IP."
echo "  Redeploy wireguard once after first start (or set Interface MTU 1280 in the UI) before adding phones."
echo "  Client DNS is the Core LAN IP (INIT_DNS). Test HTTPS on cellular after handshake."

echo
echo "DATA_ROOT=${DATA_ROOT}"
echo "Komodo Core should be at http://${NAS_LAN_IP}:9120"
echo "Log in as ${KOMODO_ADMIN_USER}."
echo "Server '${CORE_SERVER}' is KOMODO_FIRST_SERVER_NAME / PERIPHERY_CONNECT_AS."
echo "Remote Periphery should connect_as '${PERIPHERY_SERVER}'."
echo
echo "Create a ResourceSync (webhooks disabled):"
echo "  repo:            faiz-ans/infra-core"
echo "  git provider:    GitHub until Gitea exists, then gitea:3000 (see bootstrap/gitea.md)"
echo "  branch:          main"
echo "  resource path:   stacks/komodo/stacks-core.toml"
echo "  poll:            enabled"
echo "  webhook_enabled: false"
echo "After the remote Periphery server is OK, add stacks/komodo/stacks-periphery.toml."
echo "Leave restic and restic-rest deploy=false until BACKUP_DRIVE is the IronWolf."
echo
echo "Target layout:"
echo "  ${DATA_ROOT}/system/{authelia,vaultwarden,gitea,pihole,wireguard,restic,opencloud,jotty,linkding,rustdesk}"
echo "  ${DATA_ROOT}/shared/{media,downloads,files,photos,cameras}"
echo "  ${DATA_ROOT}/users/<user>/{files,photos}"
echo "  NFS exports /shared and /users to the HTPC IP only (not disk root, not system/)."
echo "  Komodo NFS_EXPORT=/shared NFS_USERS=/users"
echo "  HTPC /config is a local Docker volume; media/photos/cameras stay on NFS; OpenCloud on Core uses local binds."
echo "  First-run: bootstrap/opencloud.md, bootstrap/immich.md, bootstrap/jotty.md, bootstrap/linkding.md, bootstrap/rustdesk.md, bootstrap/adventurelog.md, bootstrap/scriberr.md, bootstrap/frigate.md."
echo "  Pi-hole stack names: pihole (Core) and pihole-periphery (HTPC)."
echo "  Router DHCP DNS: ${NAS_LAN_IP} first, then ${HTPC_UPSTREAM}. No public resolver as a third server."
echo "  Each Pi-hole fetches its own Gravity."
echo
echo "Komodo [secrets] were written to ${KOMODO_DIR}/core.config.toml"
echo "Also add remaining keys from stacks/komodo/VARIABLES.md (widget tokens, BACKUP_DRIVE on the remote host)."
echo "Follow bootstrap/periphery.md on the HTPC (firewall, Periphery env, Docker Desktop)."
echo
echo "Done."
