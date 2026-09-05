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
#
# Service layout dirs (media, cameras, files/photos, …) are root-owned with a
# sticky bit on their parents so SMB/OpenCloud users can write *inside* them
# but cannot rename, move, or delete the layout nodes themselves.
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

# Relative to shared/. Parents get sticky so these names cannot be unlinked by
# household users (they do not own the nodes after protect_layout).
PROTECTED_SHARED=(
  photos
  media
  media/tv
  media/movies
  games
  games/web
  games/assets
  games/assets/launcher
  games/assets/collection
  games/assets/category
  games/assets/source
  games/roms
  games/steam
  games/steam/steamapps
  games/steam/steamapps/downloading
  games/steam/steamapps/temp
  games/steam/steamapps/workshop
  games/steam/steamapps/shadercache
  games/steam/steamapps/common
  files
  cameras
  cameras/exports
  cameras/clips
  cameras/clips/thumbs
  cameras/clips/review
  cameras/clips/cache
  cameras/clips/export
  cameras/recordings
  downloads
  downloads/complete
  downloads/incomplete
)

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

for rel in "${PROTECTED_SHARED[@]}"; do
  mkdir -p "${DATA_ROOT}/shared/${rel}"
done

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
# OpenCloud must own config/data/posix/radicale (and the projects parent) before
# first Deploy. Do not chown -R projects/: when shared is bind-mounted there,
# recursion would rewrite the whole household tree.
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
# Placeholder files so Docker never turns these bind-mounts into directories.
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

# Root-own layout nodes; sticky on parents (find 2775 clears +t, so do this last).
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

# Drop leftover OMV ACLs on users/ (they override chmod and block even 'other').
setfacl -b "${DATA_ROOT}/users" || true
# PUID must mkdir users/<name> (OpenCloud CreateStorageSpace) and write the
# posixfs-xattr-check tempfile. root:root 755 is not enough; use group PGID
# plus an ACL (and a default ACL so new space dirs stay writable).
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

apply_home() {
  local user="$1"
  local home="${DATA_ROOT}/users/${user}"
  local parked="${DATA_ROOT}/system/opencloud/incoming/${user}"
  # Do not recreate a home that opencloud-adopt-homes.sh has parked.
  if [[ -d "${home}.__oc_incoming" || -d "${parked}" ]]; then
    echo "Skipping ${user}: parked at ${parked:-${home}.__oc_incoming}"
    echo "  Log in as ${user} (OpenCloud), then: opencloud-adopt-homes.sh restore"
    return
  fi
  mkdir -p "${home}/files" "${home}/photos"
  # Home and layout dirs are root-owned so sticky on users/ (and on the home)
  # blocks rename/delete by the household user. Contents stay writable via ACL.
  if getent group "${user}" >/dev/null; then
    chown -R "${user}:${user}" "${home}"
    chown root:"${user}" "${home}" "${home}/files" "${home}/photos"
  else
    chown -R "${user}" "${home}"
    chown root:"${user}" "${home}" "${home}/files" "${home}/photos" 2>/dev/null \
      || chown root:root "${home}" "${home}/files" "${home}/photos"
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

# users/admin is OpenCloud's built-in break-glass Personal space — leave it.
if [[ -d "${DATA_ROOT}/users/admin" ]]; then
  echo "Note: users/admin is OpenCloud local admin (break-glass), not a household home."
fi

echo "Done. Reconnect household SMB sessions. HTPC apps use NFS; remount/redeploy those stacks if needed."
echo
if [[ "${HAVE_ADMIN}" -eq 1 && ${#PRESENT_HOUSEHOLD[@]} -gt 0 ]]; then
  echo "Admin (${ADMIN}) uses:  sudo ls ${DATA_ROOT}/users/${PRESENT_HOUSEHOLD[0]}"
  echo "  (sudo cd does not work; cd is a shell builtin.)"
fi
if [[ "${HAVE_HTPC}" -eq 1 ]]; then
  echo "sudo -u ${HTPC} ls ${DATA_ROOT}/system && echo FAIL || echo system_blocked"
fi
