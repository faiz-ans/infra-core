#!/usr/bin/env bash
# Household layout + ACL/sticky after OpenCloud publish. Run on Core as root:
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root-layout.sh
#
# Creates protected dirs under shared/ (media, files, …) and users/<name>/photos.
# ACL/sticky. Requires publish bind for shared/files (or existing shared tree).
# Does not mkdir users/<name>/files (OpenCloud Personal space) or recreate
# parked OpenCloud homes (see opencloud-adopt-homes.sh).
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/data-root-defaults.sh" ]]; then
  # shellcheck source=data-root-defaults.sh
  source "${SCRIPT_DIR}/data-root-defaults.sh"
else
  echo "Copy data-root-defaults.sh next to this script (layout needs PROTECTED_SHARED)."
  echo "  scp bootstrap/data-root-defaults.sh pilot@192.168.1.110:/tmp/"
  exit 1
fi

if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT not a directory: ${DATA_ROOT}"
  exit 1
fi

have_user() { id -u "$1" >/dev/null 2>&1; }

PRESENT_HOUSEHOLD=()
for u in "${HOUSEHOLD[@]}"; do
  if have_user "${u}"; then
    PRESENT_HOUSEHOLD+=("${u}")
    usermod -aG "${SHARED_GROUP}" "${u}" 2>/dev/null || true
  else
    echo "Skipping household user ${u} (does not exist yet)."
  fi
done

HAVE_HTPC=0
if have_user "${HTPC}"; then
  HAVE_HTPC=1
  usermod -aG "${SHARED_GROUP}" "${HTPC}" 2>/dev/null || true
else
  echo "Skipping Unix user ${HTPC} (does not exist yet). NFS does not need it."
fi

HAVE_ADMIN=0
if have_user "${ADMIN}"; then
  HAVE_ADMIN=1
fi

getent group "${SHARED_GROUP}" >/dev/null || groupadd "${SHARED_GROUP}"

mkdir -p "${DATA_ROOT}/shared" "${DATA_ROOT}/users"
for rel in "${PROTECTED_SHARED[@]}"; do
  mkdir -p "${DATA_ROOT}/shared/${rel}"
done

acl_shared="g:${SHARED_GROUP}:rwx,u:${PUID}:rwx,g:${PGID}:rwx"
for u in "${PRESENT_HOUSEHOLD[@]}"; do
  acl_shared+=",u:${u}:rwx"
done
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  acl_shared+=",u:${HTPC}:rwx"
fi

chown root:"${SHARED_GROUP}" "${DATA_ROOT}/shared"
find "${DATA_ROOT}/shared" -type d -exec chmod 2775 {} +
find "${DATA_ROOT}/shared" -type f -exec chmod 664 {} +
chgrp -R "${SHARED_GROUP}" "${DATA_ROOT}/shared"
setfacl -R -m "${acl_shared}" "${DATA_ROOT}/shared"
setfacl -R -d -m "${acl_shared}" "${DATA_ROOT}/shared"

protect_shared_layout() {
  local rel d parent
  declare -A sticky_parents=()
  sticky_parents["${DATA_ROOT}"]=1
  sticky_parents["${DATA_ROOT}/shared"]=1
  for rel in "${PROTECTED_SHARED[@]}"; do
    d="${DATA_ROOT}/shared/${rel}"
    [[ -d "${d}" ]] || continue
    chown root:"${SHARED_GROUP}" "${d}"
    parent="$(dirname "${d}")"
    sticky_parents["${parent}"]=1
  done
  local p
  for p in "${!sticky_parents[@]}"; do
    [[ -d "${p}" ]] || continue
    chmod +t "${p}"
  done
}
protect_shared_layout

apply_home() {
  local user="$1"
  local home="${DATA_ROOT}/users/${user}"
  local parked="${DATA_ROOT}/system/opencloud/incoming/${user}"
  if [[ -d "${home}.__oc_incoming" || -d "${parked}" ]]; then
    echo "Skipping ${user}: parked at ${parked:-${home}.__oc_incoming}"
    echo "  Log in as ${user} (OpenCloud), then: opencloud-adopt-homes.sh restore"
    return
  fi
  if [[ ! -d "${home}" ]]; then
    echo "Skipping ${user}: no home yet (OpenCloud login creates users/${user}/files on greenfield)."
    return
  fi
  local files="${home}/files"
  if [[ ! -d "${files}" ]]; then
    echo "Skipping ${user}: no files/ space yet. Log in as ${user}, then re-run layout."
    return
  fi
  mkdir -p "${home}/photos"
  if getent group "${user}" >/dev/null; then
    chown "${user}:${user}" "${home}" 2>/dev/null || true
    chown root:"${user}" "${home}" "${files}" "${home}/photos"
  else
    chown root:"${user}" "${home}" "${files}" "${home}/photos" 2>/dev/null \
      || chown root:root "${home}" "${files}" "${home}/photos"
  fi
  find "${home}" -type d -exec chmod 700 {} +
  find "${home}" -type f -exec chmod 600 {} +
  setfacl -R -b "${home}" || true
  local home_acl="u:${user}:rwx,u:${PUID}:rwx"
  if [[ "${HAVE_HTPC}" -eq 1 ]]; then
    home_acl+=",u:${HTPC}:rwx"
  fi
  if [[ "${HAVE_ADMIN}" -eq 1 ]]; then
    home_acl+=",u:${ADMIN}:rwx"
  fi
  setfacl -R -m "${home_acl}" "${home}"
  setfacl -R -d -m "${home_acl}" "${home}"
  chmod +t "${home}"
}

for u in "${PRESENT_HOUSEHOLD[@]}"; do
  apply_home "${u}"
done

if [[ -d "${DATA_ROOT}/users/admin" ]]; then
  echo "Note: users/admin is OpenCloud local admin (break-glass), not a household home."
fi

echo "Layout done. Reconnect household SMB sessions. HTPC apps use NFS; remount/redeploy if needed."
if [[ "${HAVE_ADMIN}" -eq 1 && ${#PRESENT_HOUSEHOLD[@]} -gt 0 ]]; then
  echo "Admin (${ADMIN}) uses:  sudo ls ${DATA_ROOT}/users/${PRESENT_HOUSEHOLD[0]}"
fi
