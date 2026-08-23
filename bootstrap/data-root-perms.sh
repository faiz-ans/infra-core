#!/usr/bin/env bash
# POSIX + ACL layout for DATA_ROOT. Run on Core as root:
#   sudo bash bootstrap/data-root-perms.sh
#
#   faiz, diana  — R/W shared/ and users/<self> only (cannot enter system/)
#   periphery    — R/W shared/ and users/ (cannot enter system/)
#   pilot        — SSH admin: list/enter users/* (system/ is root-only)
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
HOUSEHOLD=(faiz diana)
HTPC=periphery
ADMIN=pilot
SHARED_GROUP=sharedwrite
HTPC_GROUP=htpc

if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT not a directory: ${DATA_ROOT}"
  exit 1
fi

for u in "${HOUSEHOLD[@]}" "${HTPC}" "${ADMIN}"; do
  if ! id -u "${u}" >/dev/null 2>&1; then
    echo "Missing Unix user: ${u}"
    exit 1
  fi
done

getent group "${SHARED_GROUP}" >/dev/null || groupadd "${SHARED_GROUP}"
getent group "${HTPC_GROUP}" >/dev/null || groupadd "${HTPC_GROUP}"

for u in "${HOUSEHOLD[@]}" "${HTPC}"; do
  usermod -aG "${SHARED_GROUP}" "${u}"
done
usermod -aG "${HTPC_GROUP}" "${HTPC}"

mkdir -p \
  "${DATA_ROOT}/system/authelia" \
  "${DATA_ROOT}/system/vaultwarden" \
  "${DATA_ROOT}/system/pihole" \
  "${DATA_ROOT}/system/wireguard" \
  "${DATA_ROOT}/system/restic" \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/users/faiz" \
  "${DATA_ROOT}/users/diana"

chown root:"${HTPC_GROUP}" "${DATA_ROOT}"
chmod 775 "${DATA_ROOT}"

# system/ is NAS-only Core app state. Do not recurse into app dirs (Docker owns them).
chown root:root "${DATA_ROOT}/system"
chmod 700 "${DATA_ROOT}/system"
setfacl -b "${DATA_ROOT}/system" || true

chown root:"${SHARED_GROUP}" "${DATA_ROOT}/shared"
find "${DATA_ROOT}/shared" -type d -exec chmod 2775 {} +
find "${DATA_ROOT}/shared" -type f -exec chmod 664 {} +
chgrp -R "${SHARED_GROUP}" "${DATA_ROOT}/shared"
setfacl -R -m "g:${SHARED_GROUP}:rwx,u:${HTPC}:rwx,u:faiz:rwx,u:diana:rwx" "${DATA_ROOT}/shared"
setfacl -R -d -m "g:${SHARED_GROUP}:rwx,u:${HTPC}:rwx,u:faiz:rwx,u:diana:rwx" "${DATA_ROOT}/shared"

# Drop leftover OMV ACLs on users/ (they override chmod and block even 'other').
setfacl -b "${DATA_ROOT}/users" || true
chown root:root "${DATA_ROOT}/users"
chmod 755 "${DATA_ROOT}/users"
setfacl -m "u:${ADMIN}:rwx,u:${HTPC}:rwx,o::rx" "${DATA_ROOT}/users"

apply_home() {
  local user="$1"
  local home="${DATA_ROOT}/users/${user}"
  mkdir -p "${home}/files" "${home}/photos"
  if getent group "${user}" >/dev/null; then
    chown -R "${user}:${user}" "${home}"
  else
    chown -R "${user}" "${home}"
  fi
  find "${home}" -type d -exec chmod 700 {} +
  find "${home}" -type f -exec chmod 600 {} +
  setfacl -R -b "${home}" || true
  setfacl -R -m "u:${user}:rwx,u:${HTPC}:rwx,u:${ADMIN}:rwx" "${home}"
  setfacl -R -d -m "u:${user}:rwx,u:${HTPC}:rwx,u:${ADMIN}:rwx" "${home}"
}

apply_home faiz
apply_home diana

echo "Done. Reconnect household SMB sessions. HTPC apps use NFS; remount/redeploy those stacks if needed."
echo
echo "Admin (pilot) uses:  sudo ls ${DATA_ROOT}/users/faiz"
echo "  (sudo cd does not work; cd is a shell builtin.)"
echo
echo "sudo -u faiz rm -f ${DATA_ROOT}/shared/_t; sudo -u faiz touch ${DATA_ROOT}/shared/_t && sudo -u faiz rm -f ${DATA_ROOT}/shared/_t"
echo "sudo -u ${HTPC} ls ${DATA_ROOT}/system && echo FAIL || echo system_blocked"
echo "sudo ls ${DATA_ROOT}/users/faiz"
