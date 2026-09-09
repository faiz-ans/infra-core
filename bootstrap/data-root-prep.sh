#!/usr/bin/env bash
# Thin DATA_ROOT prep before OpenCloud phase A. Run on Core as root:
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root-prep.sh
#
# Creates system/, empty users/, and PUID-owned OpenCloud host dirs.
# Does NOT create users/<name> homes or shared/ protected layout (see data-root-layout.sh).
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=data-root-defaults.sh
source "${SCRIPT_DIR}/data-root-defaults.sh"

if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT not a directory: ${DATA_ROOT}"
  exit 1
fi

have_user() { id -u "$1" >/dev/null 2>&1; }

HAVE_HTPC=0
if have_user "${HTPC}"; then
  HAVE_HTPC=1
else
  echo "Skipping Unix user ${HTPC} (does not exist yet). NFS does not need it."
fi

HAVE_ADMIN=0
if have_user "${ADMIN}"; then
  HAVE_ADMIN=1
else
  echo "Skipping Unix user ${ADMIN} (does not exist yet)."
fi

getent group "${SHARED_GROUP}" >/dev/null || groupadd "${SHARED_GROUP}"
getent group "${HTPC_GROUP}" >/dev/null || groupadd "${HTPC_GROUP}"

if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  usermod -aG "${SHARED_GROUP}" "${HTPC}"
  usermod -aG "${HTPC_GROUP}" "${HTPC}"
fi

mkdir -p \
  "${DATA_ROOT}/system/authelia" \
  "${DATA_ROOT}/system/vaultwarden" \
  "${DATA_ROOT}/system/gitea" \
  "${DATA_ROOT}/system/pihole" \
  "${DATA_ROOT}/system/homepage/images" \
  "${DATA_ROOT}/system/wireguard" \
  "${DATA_ROOT}/system/restic" \
  "${DATA_ROOT}/system/opencloud/config" \
  "${DATA_ROOT}/system/opencloud/data" \
  "${DATA_ROOT}/system/opencloud/posix" \
  "${DATA_ROOT}/system/opencloud/posix/projects" \
  "${DATA_ROOT}/system/opencloud/projects" \
  "${DATA_ROOT}/system/opencloud/radicale" \
  "${DATA_ROOT}/system/opencloud/radicale/collections" \
  "${DATA_ROOT}/system/jotty/data" \
  "${DATA_ROOT}/system/jotty/config" \
  "${DATA_ROOT}/system/jotty/cache" \
  "${DATA_ROOT}/system/linkding" \
  "${DATA_ROOT}/system/rustdesk" \
  "${DATA_ROOT}/system/bytestash" \
  "${DATA_ROOT}/users"

if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  chown root:"${HTPC_GROUP}" "${DATA_ROOT}"
  chmod 775 "${DATA_ROOT}"
else
  chown root:root "${DATA_ROOT}"
  chmod 755 "${DATA_ROOT}"
fi

chown root:root "${DATA_ROOT}/system"
chmod 700 "${DATA_ROOT}/system"
setfacl -b "${DATA_ROOT}/system" || true

mkdir -p \
  "${DATA_ROOT}/system/opencloud/projects" \
  "${DATA_ROOT}/system/opencloud/radicale/collections" \
  "${DATA_ROOT}/system/opencloud/posix"
chown -R "${PUID}:${PGID}" \
  "${DATA_ROOT}/system/opencloud/config" \
  "${DATA_ROOT}/system/opencloud/data" \
  "${DATA_ROOT}/system/opencloud/posix" \
  "${DATA_ROOT}/system/opencloud/radicale"
chown "${PUID}:${PGID}" "${DATA_ROOT}/system/opencloud" "${DATA_ROOT}/system/opencloud/projects"
chown -R "${PUID}:${PGID}" "${DATA_ROOT}/system/jotty"

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

setfacl -b "${DATA_ROOT}/users" || true
chown root:"${PGID}" "${DATA_ROOT}/users"
chmod 775 "${DATA_ROOT}/users"
users_acl="g:${PGID}:rwx,u:${PUID}:rwx,o::rx"
if [[ "${HAVE_ADMIN}" -eq 1 ]]; then
  users_acl="u:${ADMIN}:rwx,${users_acl}"
fi
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  users_acl="u:${HTPC}:rwx,${users_acl}"
fi
setfacl -m "${users_acl}" "${DATA_ROOT}/users"
setfacl -d -m "${users_acl}" "${DATA_ROOT}/users"
chmod +t "${DATA_ROOT}/users"

echo "Prep done: system/ + empty users/ + OpenCloud host dirs."
echo "Next (greenfield): phase-A stacks → OpenCloud login/Space shared → publish → data-root-layout.sh"
