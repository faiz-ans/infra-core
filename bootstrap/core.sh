#!/usr/bin/env bash
# Core host Layer 0 bootstrap. Copy the bootstrap/ directory to the Core machine
# (core.sh, omv-nfs.sh, data-root-prep.sh, data-root-layout.sh, komodo/) and run as root:
#   sudo bash core.sh
# Every live command is also shown in a nearby comment for copy-paste.
#
# Order: apt → external disk? → (if yes: OMV with -n -r, mount uuid path)
#        (if no: directory on OS disk) → site prompts → static LAN → Docker
#        → DATA_ROOT tree (system/<app>, not system/core) → Komodo → NFS → ACLs.

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
  komodo_save_answers
}

# Topology-driven secrets (after prompt/rand/quote_s exist).
# shellcheck source=komodo-secrets.sh
source "${SCRIPT_DIR}/komodo-secrets.sh"

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
  echo "Running vendor OMV installer with -n -r (keep NetworkManager/SSH, no reboot)."
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

# --- Site prompts (topology-driven; after storage is ready) ---
if [[ -f "${ANSWERS}" ]]; then
  # shellcheck disable=SC1090
  source "${ANSWERS}"
  echo "Loaded saved site answers from ${ANSWERS}."
  if [[ -z "${AUTHELIA_FAIZ_PASSWORD:-}" && -n "${AUTHELIA_USER_PASSWORD:-}" ]]; then
    AUTHELIA_FAIZ_PASSWORD="${AUTHELIA_USER_PASSWORD}"
  fi
fi

echo "Collecting Komodo secrets required by ${_komodo_topology} ..."
# Prefill from an existing Core config so re-runs do not rotate secrets.
if [[ -f "${KOMODO_DIR}/core.config.toml" ]]; then
  while IFS= read -r line; do
    if [[ "${line}" =~ ^([A-Z0-9_]+)[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
      k="${BASH_REMATCH[1]}"
      v="${BASH_REMATCH[2]}"
      v="${v//\\\"/\"}"
      v="${v//\\\\/\\}"
      if [[ -z "${!k-}" ]]; then
        printf -v "${k}" '%s' "${v}"
      fi
    fi
  done < <(awk '/^\[secrets\]/{p=1;next} /^\[/{p=0} p && /=/{print}' "${KOMODO_DIR}/core.config.toml")
fi
komodo_ensure_site_vars
save_answers

# Pin NAS_LAN_IP on the uplink. Router DHCP reservation is not enough
# (USB 2.5G NIC can link without a lease). Same IP as the live session.
# sudo NAS_LAN_IP=192.168.1.110 bash bootstrap/core-lan-static.sh
bash "${SCRIPT_DIR}/core-lan-static.sh"

# --- Docker ---
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker."
  # curl -fsSL https://get.docker.com | sh
  curl -fsSL https://get.docker.com | sh
  # systemctl enable --now docker
  systemctl enable --now docker
fi

# Cap container json-file logs on the OS disk (/var/lib/docker). DATA_ROOT is separate.
# sudo bash bootstrap/core-docker-engine.sh
bash "${SCRIPT_DIR}/core-docker-engine.sh"

# Host-network WireGuard NAT + IPv6 off (AAAA timeouts on dual-NIC boards).
# sudo bash bootstrap/core-net.sh
bash "${SCRIPT_DIR}/core-net.sh"

# LAN :53 REDIRECT to Pi-hole on 127.0.0.1:15353; Docker starts without wait-online.
# sudo bash bootstrap/core-lan-bind.sh
bash "${SCRIPT_DIR}/core-lan-bind.sh"

# PosixFS assimilate timer (SMB/NFS → OpenCloud). No-op until opencloud is up.
# sudo bash bootstrap/opencloud-posix-scan.sh
bash "${SCRIPT_DIR}/opencloud-posix-scan.sh"

# X1509 12V PWM cage fan (max of CPU and HDD). May ask for a reboot.
# sudo bash bootstrap/core-fan.sh
bash "${SCRIPT_DIR}/core-fan.sh"

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
  "${DATA_ROOT}/system/opencloud/radicale" \
  "${DATA_ROOT}/system/opencloud/radicale/collections" \
  "${DATA_ROOT}/system/jotty/data" \
  "${DATA_ROOT}/system/jotty/config" \
  "${DATA_ROOT}/system/jotty/cache" \
  "${DATA_ROOT}/system/linkding" \
  "${DATA_ROOT}/system/rustdesk" \
  "${DATA_ROOT}/system/bytestash" \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/shared/cameras" \
  "${DATA_ROOT}/users"
# mkdir -p "${DATA_ROOT}/users/<user>/{files,photos}" as you add household users.
# Bind-mounts must be files before first stack start. Docker creates a
# directory when the host path is missing (breaks Gitea/Komodo CA trust).
for _ca in caddy-root.crt ca-bundle.crt; do
  _capath="${DATA_ROOT}/system/authelia/${_ca}"
  if [[ -d "${_capath}" ]]; then
    rm -rf "${_capath}"
  fi
  if [[ ! -e "${_capath}" ]]; then
    : > "${_capath}"
    chmod 644 "${_capath}"
  fi
done
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
  : "${AUTHELIA_JWT_SECRET:=$(awk -F '"' '/AUTHELIA_JWT_SECRET/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")}"
  : "${AUTHELIA_SESSION_SECRET:=$(awk -F '"' '/AUTHELIA_SESSION_SECRET/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")}"
  : "${AUTHELIA_STORAGE_ENCRYPTION_KEY:=$(awk -F '"' '/AUTHELIA_STORAGE_ENCRYPTION_KEY/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")}"
fi
: "${AUTHELIA_JWT_SECRET:=$(rand)}"
: "${AUTHELIA_SESSION_SECRET:=$(rand)}"
: "${AUTHELIA_STORAGE_ENCRYPTION_KEY:=$(rand)}"
# Short names used by older comments / OIDC seeding below
AUTHELIA_JWT="${AUTHELIA_JWT_SECRET}"
AUTHELIA_SESSION="${AUTHELIA_SESSION_SECRET}"
AUTHELIA_STORAGE="${AUTHELIA_STORAGE_ENCRYPTION_KEY}"

if [[ -z "${WG_UI_PASSWORD:-}" ]]; then
  if [[ -f "${KOMODO_DIR}/core.config.toml" ]] && grep -q '^WG_UI_PASSWORD' "${KOMODO_DIR}/core.config.toml"; then
    WG_UI_PASSWORD=$(awk -F '"' '/^WG_UI_PASSWORD/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")
  else
    WG_UI_PASSWORD=$(rand)
    echo "WireGuard UI user wg-admin password (save now): ${WG_UI_PASSWORD}"
  fi
fi
: "${AUTHELIA_OIDC_HMAC_SECRET:=${AUTHELIA_OIDC_HMAC:-}}"
if [[ -z "${AUTHELIA_OIDC_HMAC_SECRET:-}" ]]; then
  if [[ -f "${KOMODO_DIR}/core.config.toml" ]] && grep -q '^AUTHELIA_OIDC_HMAC_SECRET' "${KOMODO_DIR}/core.config.toml"; then
    AUTHELIA_OIDC_HMAC_SECRET=$(awk -F '"' '/^AUTHELIA_OIDC_HMAC_SECRET/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")
  else
    AUTHELIA_OIDC_HMAC_SECRET=$(rand)
  fi
fi
AUTHELIA_OIDC_HMAC="${AUTHELIA_OIDC_HMAC_SECRET}"
if [[ -z "${OIDC_CLIENT_SECRET:-}" ]]; then
  if [[ -f "${KOMODO_DIR}/core.config.toml" ]] && grep -q '^OIDC_CLIENT_SECRET' "${KOMODO_DIR}/core.config.toml"; then
    OIDC_CLIENT_SECRET=$(awk -F '"' '/^OIDC_CLIENT_SECRET/ {print $2; exit}' "${KOMODO_DIR}/core.config.toml")
  else
    OIDC_CLIENT_SECRET=$(openssl rand -hex 32)
  fi
fi

# OIDC JWKS + hashed client secret (Authelia reads these from DATA_ROOT).
authelia_dir="${DATA_ROOT}/system/authelia"
mkdir -p "${authelia_dir}"
if [[ ! -f "${authelia_dir}/oidc.pem" ]]; then
  oidc_tmp=$(mktemp -d)
  docker run --rm -v "${oidc_tmp}:/out" authelia/authelia:4 \
    authelia crypto pair rsa generate --directory /out
  if [[ -f "${oidc_tmp}/private.pem" ]]; then
    cp "${oidc_tmp}/private.pem" "${authelia_dir}/oidc.pem"
  elif [[ -f "${oidc_tmp}/key.pem" ]]; then
    cp "${oidc_tmp}/key.pem" "${authelia_dir}/oidc.pem"
  else
    echo "Failed to generate Authelia OIDC signing key."
    ls -la "${oidc_tmp}"
    exit 1
  fi
  rm -rf "${oidc_tmp}"
  chmod 600 "${authelia_dir}/oidc.pem"
fi
if [[ ! -f "${authelia_dir}/client_secret_digest" ]]; then
  OIDC_DIGEST=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate pbkdf2 --variant sha512 --password "${OIDC_CLIENT_SECRET}" \
    | awk '/^Digest:/ {print $2}')
  if [[ -z "${OIDC_DIGEST}" ]]; then
    echo "Failed to hash OIDC client secret."
    exit 1
  fi
  printf '%s' "${OIDC_CLIENT_SECRET}" > "${authelia_dir}/client_secret"
  printf '%s' "${OIDC_DIGEST}" > "${authelia_dir}/client_secret_digest"
  chmod 600 "${authelia_dir}/client_secret" "${authelia_dir}/client_secret_digest"
fi
if [[ -d "${authelia_dir}/caddy-root.crt" ]]; then
  rm -rf "${authelia_dir}/caddy-root.crt"
fi
if docker ps -qf name=^caddy$ | grep -q .; then
  docker exec caddy cat /data/caddy/pki/authorities/local/root.crt > "${authelia_dir}/caddy-root.crt"
  chmod 644 "${authelia_dir}/caddy-root.crt"
  if [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
    cat /etc/ssl/certs/ca-certificates.crt "${authelia_dir}/caddy-root.crt" > "${authelia_dir}/ca-bundle.crt"
  else
    cp "${authelia_dir}/caddy-root.crt" "${authelia_dir}/ca-bundle.crt"
  fi
  chmod 644 "${authelia_dir}/ca-bundle.crt"
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
DOMAIN=${DOMAIN}
NAS_LAN_IP=${NAS_LAN_IP}
DATA_ROOT=${DATA_ROOT}
KOMODO_HOST=https://ops.${DOMAIN}
KOMODO_TITLE=Komodo
KOMODO_LOCAL_AUTH=true
KOMODO_OIDC_ENABLED=true
KOMODO_OIDC_PROVIDER=https://auth.${DOMAIN}
KOMODO_OIDC_CLIENT_ID=komodo
KOMODO_OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}
KOMODO_INIT_ADMIN_USERNAME=${KOMODO_ADMIN_USER}
KOMODO_INIT_ADMIN_PASSWORD=${KOMODO_ADMIN_PASSWORD}
KOMODO_FIRST_SERVER_NAME=${CORE_SERVER}
KOMODO_PERIPHERY_PUBLIC_KEY=file:/config/keys/periphery.pub
KOMODO_DISABLE_USER_REGISTRATION=false
KOMODO_DISABLE_LOCAL_USER_REGISTRATION=true
KOMODO_DISABLE_OIDC_USER_REGISTRATION=false
KOMODO_ENABLE_NEW_USERS=true
KOMODO_DISABLE_CONFIRM_DIALOG=true
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

# Write only secrets required by topology (plus always-on platform keys).
AUTHELIA_JWT_SECRET="${AUTHELIA_JWT}"
AUTHELIA_SESSION_SECRET="${AUTHELIA_SESSION}"
AUTHELIA_STORAGE_ENCRYPTION_KEY="${AUTHELIA_STORAGE}"
AUTHELIA_OIDC_HMAC_SECRET="${AUTHELIA_OIDC_HMAC}"
komodo_write_core_secrets
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

# --- Thin prep (system/ + empty users/ + OpenCloud dirs). Full shared layout is
# data-root-layout.sh after OpenCloud publish (greenfield). See bootstrap/opencloud.md. ---
if [[ -f "${REPO_BOOTSTRAP}/data-root-prep.sh" ]]; then
  # sudo DATA_ROOT=<DATA_ROOT> bash bootstrap/data-root-prep.sh
  DATA_ROOT="${DATA_ROOT}" bash "${REPO_BOOTSTRAP}/data-root-prep.sh"
fi

# --- Authelia users file (hash via official image) ---
# docker run --rm authelia/authelia:4 authelia crypto hash generate argon2 --password '...'
users_file="${DATA_ROOT}/system/authelia/users.yml"
if [[ -d "${users_file}" ]]; then
  echo "Replacing directory ${users_file} (Docker created it when the file was missing)."
  rm -rf "${users_file}"
fi
if [[ ! -f "${users_file}" ]] || ! grep -q '^    password: '\''\$' "${users_file}"; then
  FAIZ_HASH=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate argon2 --password "${AUTHELIA_FAIZ_PASSWORD}" \
    | awk '/^Digest:/ {print $2}')
  DIANA_HASH=$(docker run --rm authelia/authelia:4 \
    authelia crypto hash generate argon2 --password "${AUTHELIA_DIANA_PASSWORD}" \
    | awk '/^Digest:/ {print $2}')
  if [[ -z "${FAIZ_HASH}" ]]; then
    FAIZ_HASH="\$plaintext\$${AUTHELIA_FAIZ_PASSWORD}"
  fi
  if [[ -z "${DIANA_HASH}" ]]; then
    DIANA_HASH="\$plaintext\$${AUTHELIA_DIANA_PASSWORD}"
  fi
  cat > "${users_file}" <<EOF
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
echo "Create a Komodo Repo (leave Server empty), then a ResourceSync (webhooks disabled):"
echo "  Repo name:       infra-core   (must match topology.inc linked_repo)"
echo "  repo:            faiz-ans/infra-core"
echo "  git provider:    GitHub until Gitea exists, then gitea:3000 (see bootstrap/gitea.md)"
echo "  branch:          main"
echo "  ResourceSync:    Select Repo → infra-core"
echo "  resource path:   stacks/komodo/stacks-bootstrap.toml  (phase A)"
echo "  then:            stacks/komodo/stacks-core.toml (+ stacks-periphery.toml)"
echo "  poll:            enabled"
echo "  webhook_enabled: false"
echo "After the remote Periphery server is OK, add stacks/komodo/stacks-periphery.toml."
echo "Leave restic and restic-rest deploy=false until BACKUP_DRIVE is the IronWolf."
echo
echo "Target layout:"
echo "  ${DATA_ROOT}/system/{authelia,vaultwarden,gitea,pihole,wireguard,restic,opencloud,jotty,linkding,rustdesk,bytestash}"
echo "  ${DATA_ROOT}/shared/{media,downloads,files,photos,cameras}"
echo "  ${DATA_ROOT}/users/<user>/{files,photos}"
echo "  NFS exports /shared and /users to the HTPC IP only (not a LAN /24, not disk root, not system/)."
echo "  Komodo NFS_EXPORT=/shared NFS_USERS=/users"
echo "  HTPC /config is a local Docker volume; media/photos/cameras stay on NFS; OpenCloud on Core uses local binds."
echo "  After ResourceSync deploys caddy, it writes system/authelia/caddy-root.crt (Gitea/Komodo TLS)."
echo "  Core Docker log caps: /etc/docker/daemon.json (core-docker-engine.sh). Recreate containers after first apply."
echo "  HTPC: bootstrap/periphery-docker-engine.ps1 (pools + logs + DiskSizeMiB); Deploy periphery stacks one at a time first."
echo "  Cage fan: sudo bash bootstrap/core-fan.sh (PWM from max CPU/HDD; see bootstrap/core-fan.md)."
echo "  After reboot: core-lan-bind.service REDIRECTs NAS_LAN_IP:53 to 127.0.0.1:15353. Host DNS is 127.0.0.1:15353 (not the LAN REDIRECT)."
echo "  OpenCloud SMB/NFS assimilate: opencloud-posix-scan.timer (posixfs scan /posix/users and /posix/projects)."
echo "  Core LAN IPv4 is static ${NAS_LAN_IP} (core-lan-static.sh). Do not depend on a router DHCP reservation for the NAS address."
echo "  First-run: bootstrap/authelia.md, bootstrap/vaultwarden.md, bootstrap/opencloud.md, bootstrap/immich.md, bootstrap/jotty.md, bootstrap/linkding.md, bootstrap/rustdesk.md, bootstrap/adventurelog.md, bootstrap/scriberr.md, bootstrap/frigate.md, bootstrap/transmute.md, bootstrap/bentopdf.md, bootstrap/libretranslate.md, bootstrap/openreader.md, bootstrap/it-tools.md, bootstrap/n8n.md, bootstrap/bytestash.md, bootstrap/glances.md."
echo "  Pi-hole stack names: pihole (Core) and pihole-periphery (HTPC)."
echo "  Router DHCP DNS: ${NAS_LAN_IP} first, then ${HTPC_UPSTREAM}. No public resolver as a third server."
echo "  Each Pi-hole fetches its own Gravity."
echo
echo "Komodo [secrets] were written to ${KOMODO_DIR}/core.config.toml (topology-filtered)."
echo "After adding stacks to topology.inc: sudo bash bootstrap/sync-komodo-secrets.sh"
echo "Homepage widget API keys stay empty until you set them via sync or answers (not the Komodo UI)."
echo "Follow bootstrap/periphery.md on the HTPC (Docker Desktop engine script, firewall, Periphery env)."
echo
echo "Done."
