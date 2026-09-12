#!/usr/bin/env bash
# Household documents: OpenCloud Project Space "shared" = DATA_ROOT/shared/files.
# media/photos/games/downloads/cameras stay siblings under shared/ (SMB/NFS only).
#
# CreateStorageSpace refuses an existing path. Parent bind
# system/opencloud/projects → /posix/projects; OpenCloud mkdir's projects/shared;
# we bind that onto shared/files.
#
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh park
#   # browser: Spaces → New Space → name exactly "shared"; add household members
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh publish
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh restore
#
# Existing site (space was bound to whole shared/):
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-shared.sh narrow
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=data-root-defaults.sh
source "${SCRIPT_DIR}/data-root-defaults.sh"

SHARED="${DATA_ROOT}/shared"
FILES="${SHARED}/files"
PROJECTS="${DATA_ROOT}/system/opencloud/projects"
SPACE="${PROJECTS}/shared"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"
PARKED="${INCOMING}/shared"
FSTAB_TAG="opencloud-shared-bind"

usage() {
  echo "Usage: $0 park|publish|restore|narrow|status"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

inode() {
  stat -c '%d:%i' "$1"
}

published() {
  [[ -d "${SPACE}" && -d "${FILES}" ]] || return 1
  [[ "$(inode "${FILES}")" == "$(inode "${SPACE}")" ]]
}

published_whole() {
  [[ -d "${SPACE}" && -d "${SHARED}" ]] || return 1
  [[ "$(inode "${SHARED}")" == "$(inode "${SPACE}")" ]]
}

write_fstab() {
  local dest=$1
  if grep -q "${FSTAB_TAG}" /etc/fstab 2>/dev/null; then
    sed -i "/${FSTAB_TAG}/d" /etc/fstab
  fi
  echo "${SPACE} ${dest} none bind 0 0  # ${FSTAB_TAG}" >> /etc/fstab
}

status() {
  echo "shared/:       ${SHARED}"
  echo "shared/files/: ${FILES}"
  echo "space/:        ${SPACE}"
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
    echo "  publish: OK (shared/files and projects/shared are the same inode)"
  elif published_whole; then
    echo "  publish: WHOLE shared/ is still the space (run narrow)"
  else
    echo "  publish: NOT bound to shared/files"
  fi
  if [[ -d "${PARKED}" ]]; then
    echo "  parked content: ${PARKED}"
  fi
}

park() {
  if published || published_whole; then
    echo "skip: shared space already published (use narrow if the bind is still whole shared/)"
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

  docker stop opencloud
  mkdir -p "${INCOMING}" "${PROJECTS}"
  chown "${PUID}:${PGID}" "${PROJECTS}" 2>/dev/null || true
  mv "${SHARED}" "${PARKED}"
  mkdir -p "${SHARED}"
  chown root:"${SHARED_GROUP}" "${SHARED}" 2>/dev/null || chown root:root "${SHARED}"
  chmod 2775 "${SHARED}"
  docker start opencloud
  echo
  echo "Parked shared content -> system/opencloud/incoming/shared"
  echo "1. Browser: Spaces → New Space → name exactly: shared; add household members."
  echo "2. $0 publish"
  echo "3. $0 restore"
}

publish() {
  mkdir -p "${PROJECTS}" "${SHARED}"
  if [[ ! -d "${SPACE}" ]]; then
    echo "refusing: ${SPACE} missing. Create Project Space named exactly shared first."
    exit 1
  fi
  if [[ -z "$(space_id "${SPACE}")" ]]; then
    echo "refusing: ${SPACE} has no user.oc.space.id."
    echo "Create Project Space named exactly shared, then retry."
    exit 1
  fi
  if published; then
    echo "already published: $(inode "${FILES}") == $(inode "${SPACE}")"
    write_fstab "${FILES}"
    return 0
  fi
  if published_whole; then
    echo "refusing: whole shared/ is still the space bind. Run: $0 narrow"
    exit 1
  fi
  mkdir -p "${FILES}"
  if find "${FILES}" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    echo "refusing: ${FILES} is not empty and is not yet a bind of ${SPACE}."
    echo "Move document trees into ${SPACE}/, empty ${FILES}, then retry."
    exit 1
  fi
  mount --bind "${SPACE}" "${FILES}"
  if ! published; then
    echo "refusing: mount --bind ran but inodes still differ"
    exit 1
  fi
  write_fstab "${FILES}"
  echo "mounted ${SPACE} -> ${FILES}"
  echo "SMB/NFS root ${SHARED} is unchanged. OpenCloud sees documents only."
  echo "Run: $0 restore  (if content was parked)"
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
    echo "refusing: ${FILES} is not bind-mounted to ${SPACE}. Run publish first."
    exit 1
  fi

  docker stop opencloud
  local item name dest
  shopt -s dotglob nullglob
  for item in "${PARKED}"/*; do
    name="$(basename "${item}")"
    if [[ "${name}" == "files" ]]; then
      dest="${FILES}"
    else
      dest="${SHARED}/${name}"
    fi
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
  echo "Scanning documents space:"
  docker exec opencloud opencloud posixfs scan /posix/projects/shared || true
  echo
  echo "Re-run data-root-layout.sh to restore household ACLs (xattrs are kept)."
  echo "Then: DATA_ROOT=${DATA_ROOT} bash bootstrap/opencloud-check.sh"
}

narrow() {
  if published; then
    echo "already narrow: shared/files is the space bind"
    write_fstab "${FILES}"
    exit 0
  fi
  if [[ -z "$(space_id "${SPACE}")" ]]; then
    echo "refusing: ${SPACE} has no user.oc.space.id"
    exit 1
  fi
  if ! published_whole; then
    echo "refusing: whole shared/ is not the current space bind."
    echo "If this is greenfield, use publish (empty shared/files)."
    echo "shared=$(inode "${SHARED}" 2>/dev/null || echo missing) space=$(inode "${SPACE}" 2>/dev/null || echo missing)"
    exit 1
  fi

  docker stop opencloud
  umount "${SHARED}" || umount -l "${SHARED}"
  mkdir -p "${SHARED}"
  shopt -s dotglob nullglob
  local item
  for item in "${SPACE}"/*; do
    mv "${item}" "${SHARED}/"
  done
  shopt -u dotglob nullglob
  if [[ -d "${SHARED}/files" ]]; then
    shopt -s dotglob nullglob
    for item in "${SHARED}/files"/*; do
      mv "${item}" "${SPACE}/"
    done
    shopt -u dotglob nullglob
    rmdir "${SHARED}/files"
  fi
  mkdir -p "${FILES}"
  if find "${FILES}" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
    echo "refusing: ${FILES} not empty after flatten"
    exit 1
  fi
  mount --bind "${SPACE}" "${FILES}"
  if ! published; then
    echo "refusing: bind to shared/files failed"
    exit 1
  fi
  write_fstab "${FILES}"
  docker start opencloud
  echo "Narrowed OpenCloud shared space to ${FILES} (media/games stay under ${SHARED})."
  docker exec opencloud opencloud posixfs scan /posix/projects/shared || true
}

case "$1" in
  park) park ;;
  publish) publish ;;
  restore) restore ;;
  narrow) narrow ;;
  status) status ;;
  *) usage ;;
esac
