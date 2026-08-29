#!/usr/bin/env bash
# POSIX + ACL layout for DATA_ROOT. Run on Core as root:
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root-perms.sh
#
# Unix users that exist get ACLs. Missing household names are skipped so a
# fresh Pi (only the SSH admin) can still lock system/ and mode shared/.
#
#   household   — R/W shared/ and users/<self> only (cannot enter system/)
#   periphery   — R/W shared/ and users/ (cannot enter system/)
#   SSH admin   — list/enter users/* (system/ is root-only)
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
HOUSEHOLD=(faiz diana)
HTPC=periphery
ADMIN=pilot
SHARED_GROUP=sharedwrite
HTPC_GROUP=htpc

if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT not a directory: ${DATA_ROOT}"
  exit 1
fi

have_user() { id -u "$1" >/dev/null 2>&1; }

PRESENT_HOUSEHOLD=()
for u in "${HOUSEHOLD[@]}"; do
  if have_user "${u}"; then
    PRESENT_HOUSEHOLD+=("${u}")
  else
    echo "Skipping household user ${u} (does not exist yet)."
  fi
done

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

for u in "${PRESENT_HOUSEHOLD[@]}"; do
  usermod -aG "${SHARED_GROUP}" "${u}"
done
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  usermod -aG "${SHARED_GROUP}" "${HTPC}"
  usermod -aG "${HTPC_GROUP}" "${HTPC}"
fi

mkdir -p \
  "${DATA_ROOT}/system/authelia" \
  "${DATA_ROOT}/system/vaultwarden" \
  "${DATA_ROOT}/system/gitea" \
  "${DATA_ROOT}/system/pihole" \
  "${DATA_ROOT}/system/wireguard" \
  "${DATA_ROOT}/system/restic" \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/media/movies" \
  "${DATA_ROOT}/shared/media/tv" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/downloads/complete" \
  "${DATA_ROOT}/shared/downloads/incomplete" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/users"

if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  chown root:"${HTPC_GROUP}" "${DATA_ROOT}"
  chmod 775 "${DATA_ROOT}"
else
  chown root:root "${DATA_ROOT}"
  chmod 755 "${DATA_ROOT}"
fi

# system/ is NAS-only Core app state. Do not recurse into app dirs (Docker owns them).
chown root:root "${DATA_ROOT}/system"
chmod 700 "${DATA_ROOT}/system"
setfacl -b "${DATA_ROOT}/system" || true

# linuxserver containers (Radarr/qBit/Jellyfin) write as PUID:PGID over NFS.
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

# Drop leftover OMV ACLs on users/ (they override chmod and block even 'other').
setfacl -b "${DATA_ROOT}/users" || true
chown root:root "${DATA_ROOT}/users"
chmod 755 "${DATA_ROOT}/users"
users_acl="o::rx"
if [[ "${HAVE_ADMIN}" -eq 1 ]]; then
  users_acl="u:${ADMIN}:rwx,${users_acl}"
fi
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  users_acl="u:${HTPC}:rwx,${users_acl}"
fi
setfacl -m "${users_acl}" "${DATA_ROOT}/users"

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
  local home_acl="u:${user}:rwx"
  if [[ "${HAVE_HTPC}" -eq 1 ]]; then
    home_acl+=",u:${HTPC}:rwx"
  fi
  if [[ "${HAVE_ADMIN}" -eq 1 ]]; then
    home_acl+=",u:${ADMIN}:rwx"
  fi
  setfacl -R -m "${home_acl}" "${home}"
  setfacl -R -d -m "${home_acl}" "${home}"
}

for u in "${PRESENT_HOUSEHOLD[@]}"; do
  apply_home "${u}"
done

echo "Done. Reconnect household SMB sessions. HTPC apps use NFS; remount/redeploy those stacks if needed."
echo
if [[ "${HAVE_ADMIN}" -eq 1 && ${#PRESENT_HOUSEHOLD[@]} -gt 0 ]]; then
  echo "Admin (${ADMIN}) uses:  sudo ls ${DATA_ROOT}/users/${PRESENT_HOUSEHOLD[0]}"
  echo "  (sudo cd does not work; cd is a shell builtin.)"
fi
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  echo "sudo -u ${HTPC} ls ${DATA_ROOT}/system && echo FAIL || echo system_blocked"
fi
