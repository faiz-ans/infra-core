#!/usr/bin/env bash
# Household ${DATA_ROOT}/shared as OpenCloud Project Space "shared".
#
# CreateStorageSpace refuses a path that already exists. Binding shared/ as
# the space root therefore always fails. Same pattern as personal homes:
# parent bind system/opencloud/projects → /posix/projects; OpenCloud mkdir's
# projects/shared with xattrs; we bind-mount that onto DATA_ROOT/shared for
# SMB/NFS.
#
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-adopt-shared.sh park
#   # Redeploy opencloud if compose still had shared→/posix/projects/shared
#   # browser: Spaces → New Space → name exactly "shared"; add diana
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh publish
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh restore
#
# park moves content to system/opencloud/incoming/shared. Immich sees empty
# shared/ until publish+restore.
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
SHARED="${DATA_ROOT}/shared"
PROJECTS="${DATA_ROOT}/system/opencloud/projects"
SPACE="${PROJECTS}/shared"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"
PARKED="${INCOMING}/shared"
FSTAB_TAG="opencloud-shared-bind"

usage() {
  echo "Usage: $0 park|publish|restore|status"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

published() {
  # Same device+inode means SHARED is a bind of SPACE (not merely "on the data disk").
  [[ -d "${SPACE}" && -d "${SHARED}" ]] || return 1
  [[ "$(stat -c '%d:%i' "${SHARED}")" == "$(stat -c '%d:%i' "${SPACE}")" ]]
}

status() {
  echo "shared/: ${SHARED}"
  echo "space/:  ${SPACE}"
  if [[ -d "${SPACE}" ]]; then
    local sid
    sid="$(space_id "${SPACE}")"
    if [[ -n "${sid}" ]]; then
      echo "  space id ${sid}"
    else
      echo "  no user.oc.space.id on projects/shared"
    fi
  else
    echo "  projects/shared missing (create Space named shared after Redeploy)"
  fi
  if published; then
    echo "  publish: OK (shared and projects/shared are the same inode)"
  else
    echo "  publish: NOT bound (run publish after create; do not trust findmnt alone)"
  fi
  if [[ -d "${PARKED}" ]]; then
    echo "  parked content: ${PARKED}"
  fi
}

park() {
  if [[ -n "$(space_id "${SPACE}" 2>/dev/null || true)" ]] && published; then
    echo "skip: shared space already published"
    exit 0
  fi
  if [[ -e "${PARKED}" ]]; then
    echo "refusing: ${PARKED} already exists"
    exit 1
  fi
  if [[ ! -d "${SHARED}" ]]; then
    echo "refusing: ${SHARED} missing"
    exit 1
  fi
  if published; then
    echo "refusing: ${SHARED} is already the space bind. umount it first if re-parking."
    exit 1
  fi

  docker stop opencloud
  mkdir -p "${INCOMING}" "${PROJECTS}"
  chown "${PUID:-1000}:${PGID:-1000}" "${PROJECTS}" 2>/dev/null || true
  mv "${SHARED}" "${PARKED}"
  mkdir -p "${SHARED}"
  chown root:sharedwrite "${SHARED}" 2>/dev/null || chown root:root "${SHARED}"
  chmod 2775 "${SHARED}"
  docker start opencloud
  echo
  echo "Parked shared content -> system/opencloud/incoming/shared"
  echo "1. Komodo → opencloud → Redeploy (projects parent bind, not shared leaf)."
  echo "2. Browser: Spaces → New Space → name exactly: shared; add diana."
  echo "3. $0 publish"
  echo "4. $0 restore"
}

publish() {
  mkdir -p "${PROJECTS}"
  if [[ ! -d "${SPACE}" ]]; then
    echo "refusing: ${SPACE} missing. Create Project Space named exactly shared first."
    exit 1
  fi
  if [[ -z "$(space_id "${SPACE}")" ]]; then
    echo "refusing: ${SPACE} has no user.oc.space.id."
    echo "Create Project Space named exactly shared, then retry."
    exit 1
  fi
  if [[ ! -d "${SHARED}" ]]; then
    mkdir -p "${SHARED}"
  fi
  if published; then
    echo "already published: $(stat -c '%d:%i' "${SHARED}") == $(stat -c '%d:%i' "${SPACE}")"
  else
    # Mountpoint must be empty (content belongs in SPACE, then bind)
    if find "${SHARED}" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
      echo "refusing: ${SHARED} is not empty and is not yet a bind of ${SPACE}."
      echo "If restore already ran into shared/ by mistake, move those dirs into"
      echo "  ${SPACE}/"
      echo "then re-run publish (empty shared/, then mount --bind)."
      exit 1
    fi
    mount --bind "${SPACE}" "${SHARED}"
    if ! published; then
      echo "refusing: mount --bind ran but inodes still differ"
      exit 1
    fi
    echo "mounted ${SPACE} -> ${SHARED}"
  fi
  if ! grep -q "${FSTAB_TAG}" /etc/fstab 2>/dev/null; then
    echo "${SPACE} ${SHARED} none bind 0 0  # ${FSTAB_TAG}" >> /etc/fstab
    echo "added fstab line (${FSTAB_TAG})"
  fi
  echo
  echo "SMB/NFS path ${SHARED} is now the OpenCloud space. Run: $0 restore"
}

restore() {
  if [[ ! -d "${PARKED}" ]]; then
    echo "skip: no parked content at ${PARKED}"
    exit 0
  fi
  if [[ -z "$(space_id "${SPACE}")" ]]; then
    echo "refusing: ${SPACE} has no user.oc.space.id. create + publish first."
    exit 1
  fi
  if ! published; then
    echo "refusing: ${SHARED} is not bind-mounted to ${SPACE}. Run publish first."
    echo "Check: stat -c '%d:%i' ${SHARED} ${SPACE}"
    exit 1
  fi

  docker stop opencloud
  local item name dest
  shopt -s dotglob nullglob
  for item in "${PARKED}"/*; do
    name="$(basename "${item}")"
    dest="${SHARED}/${name}"
    if [[ -e "${dest}" ]]; then
      if [[ -d "${item}" && -d "${dest}" ]]; then
        find "${item}" -mindepth 1 -maxdepth 1 -exec mv -t "${dest}" {} +
        rmdir "${item}" 2>/dev/null || {
          echo "could not empty ${item}; leaving parked files"
          exit 1
        }
      else
        echo "refusing: ${dest} exists and is not a mergeable directory"
        exit 1
      fi
    else
      mv "${item}" "${dest}"
    fi
  done
  shopt -u dotglob nullglob
  rmdir "${PARKED}"
  docker start opencloud
  echo "Scanning project space (large trees like media/games take time):"
  docker exec opencloud opencloud posixfs scan /posix/projects/shared || true
  echo
  echo "Re-run data-root-perms.sh to restore household ACLs (xattrs are kept)."
  echo "Then: DATA_ROOT=${DATA_ROOT} bash bootstrap/opencloud-check.sh"
}

case "$1" in
  park) park ;;
  publish) publish ;;
  restore) restore ;;
  status) status ;;
  *) usage ;;
esac
