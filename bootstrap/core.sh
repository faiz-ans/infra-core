#!/usr/bin/env bash
# Core host Layer 0 bootstrap. Copy the bootstrap/ directory to the Core machine
# and run as root:
#   sudo bash core.sh
# Order: apt → disk/OMV → site prompts → static LAN → Podman + Cockpit
#        → DATA_ROOT prep. Does not install Materia, lan-bind, NFS, or stacks.

set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

INFRA_DIR=/etc/infra-core
ANSWERS="${INFRA_DIR}/bootstrap-answers.env"
STATE="${INFRA_DIR}/bootstrap-state.env"
SITE_ENV="${INFRA_DIR}/site.env"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_BOOTSTRAP="${SCRIPT_DIR}"
# If you copied only this script, set REPO_BOOTSTRAP to a clone of infra-core/bootstrap.

mkdir -p "${INFRA_DIR}"

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
  site_save_answers
}

# Topology-driven secrets (after prompt/rand/quote_s exist).
# shellcheck source=core/site-secrets.sh
source "${SCRIPT_DIR}/core/site-secrets.sh"

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
  systemctl restart monit 2>/dev/null || true
  omv-salt deploy run nginx || {
    echo "omv-salt nginx failed; workbench may stay on :80 until you retry after monit is up."
  }

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

echo "Collecting site secrets ..."
site_ensure_site_vars
save_answers
site_write_site_env

# Pin NAS_LAN_IP on the uplink. Router DHCP reservation is not enough
# (USB 2.5G NIC can link without a lease). Same IP as the live session.
# sudo NAS_LAN_IP=192.168.1.110 bash bootstrap/core/core-lan-static.sh
bash "${SCRIPT_DIR}/core/core-lan-static.sh"

# Podman + Cockpit (not Materia).
bash "${SCRIPT_DIR}/core/podman-install.sh"

# Host-network WireGuard NAT + IPv6 off (AAAA timeouts on dual-NIC boards).
# Public DNS until Pi-hole exists.
# sudo bash bootstrap/core/core-net.sh
CORE_DNS_MODE=public bash "${SCRIPT_DIR}/core/core-net.sh"

# Install lan-bind units disabled. Do not enable until Pi-hole and Caddy listen.
bash "${SCRIPT_DIR}/core/core-lan-bind.sh" --install-only

# PosixFS assimilate timer (SMB/NFS → OpenCloud). No-op until opencloud is up.
# sudo bash bootstrap/opencloud/opencloud-posix-scan.sh
bash "${SCRIPT_DIR}/opencloud/opencloud-posix-scan.sh"

# X1509 12V PWM cage fan (max of CPU and HDD). May ask for a reboot.
# sudo bash bootstrap/core/core-fan.sh
bash "${SCRIPT_DIR}/core/core-fan.sh"

# USB CyberPower ST625U: NUT monitor + low-battery shutdown.
if command -v omv-rpc >/dev/null 2>&1 && [[ -f "${REPO_BOOTSTRAP}/omv/omv-nut.sh" ]]; then
  bash "${REPO_BOOTSTRAP}/omv/omv-nut.sh"
fi


# --- Thin prep (system/ + empty users/ + OpenCloud dirs). Full shared layout is
# data-root-layout.sh after OpenCloud publish. See bootstrap/first-run/opencloud.md. ---
if [[ -f "${REPO_BOOTSTRAP}/data-root/data-root-prep.sh" ]]; then
  DATA_ROOT="${DATA_ROOT}" bash "${REPO_BOOTSTRAP}/data-root/data-root-prep.sh"
fi

# OIDC JWKS + hashed client secret. Skip files that already exist (remount).
authelia_dir="${DATA_ROOT}/system/authelia"
mkdir -p "${authelia_dir}"
if [[ ! -f "${authelia_dir}/oidc.pem" ]]; then
  oidc_tmp=$(mktemp -d)
  podman run --rm -v "${oidc_tmp}:/out" docker.io/authelia/authelia:4 \
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
  OIDC_DIGEST=$(podman run --rm docker.io/authelia/authelia:4 \
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

site_write_site_env
chmod 600 "${ANSWERS}" "${SITE_ENV}" 2>/dev/null || true

users_file="${DATA_ROOT}/system/authelia/users.yml"
if [[ -d "${users_file}" ]]; then
  echo "Replacing directory ${users_file} (a previous bootstrap created it when the file was missing)."
  rm -rf "${users_file}"
fi
if [[ ! -f "${users_file}" ]]; then
  FAIZ_HASH=$(podman run --rm docker.io/authelia/authelia:4 \
    authelia crypto hash generate argon2 --password "${AUTHELIA_FAIZ_PASSWORD}" \
    | awk '/^Digest:/ {print $2}')
  DIANA_HASH=$(podman run --rm docker.io/authelia/authelia:4 \
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
else
  echo "Keeping existing ${users_file}"
fi

echo
echo "DATA_ROOT=${DATA_ROOT}"
echo "site.env: ${SITE_ENV}"
echo "Cockpit: https://${NAS_LAN_IP}:9090 (or https://box.${DOMAIN} after Caddy)."
echo
echo "Layer 0 done. Materia was not installed."
echo "Check DOMAIN/NAS_LAN_IP/SURFACE_UPSTREAM/WG_HOST in ${SITE_ENV} before apply."
echo
echo "Next:"
echo "  sudo bash bootstrap/apply.sh --role core-bootstrap"
echo "  Wait until :15353 :8080 :8443 listen, then:"
echo "    sudo bash bootstrap/core/core-lan-bind.sh --enable"
echo "  OpenCloud spaces (or verify existing xattrs) → data-root-layout.sh → OMV NFS."
echo "  Then add core-full in MANIFEST.toml and: sudo bash bootstrap/apply.sh --role core-full"
echo "  Optional GitOps poller (this lab only): sudo bash bootstrap/core/materia-enable.sh"
echo "  Runbook: bootstrap/SITE-DEPLOY.md"
echo
echo "Done."
