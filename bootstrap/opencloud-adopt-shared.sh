#!/usr/bin/env bash
# OpenCloud CreateStorageSpace refuses a path that already exists and does
# not stamp xattrs. Household ${DATA_ROOT}/shared is bound at
# /posix/projects/shared (Space name must be exactly "shared").
#
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-adopt-shared.sh park
#   # browser: Spaces → New Space → name exactly "shared"; add faiz + diana
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-adopt-shared.sh restore
#
# park moves shared content to system/opencloud/incoming/shared and leaves an
# empty shared/ so NFS/SMB paths stay valid. Immich will see an empty tree
# until restore — pause Immich library scans if you care.
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
SHARED="${DATA_ROOT}/shared"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"
PARKED="${INCOMING}/shared"

usage() {
  echo "Usage: $0 park|restore|status"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

status() {
  echo "shared/: ${SHARED}"
  if [[ ! -d "${SHARED}" ]]; then
    echo "missing"
    return
  fi
  local sid
  sid="$(space_id "${SHARED}")"
  if [[ -n "${sid}" ]]; then
    echo "  space id ${sid}"
  else
    echo "  no user.oc.space.id"
  fi
  if [[ -d "${PARKED}" ]]; then
    echo "  parked content: ${PARKED}"
  fi
}

park() {
  if [[ -n "$(space_id "${SHARED}")" ]]; then
    echo "skip: ${SHARED} already has user.oc.space.id"
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
  mkdir -p "${INCOMING}"
  mv "${SHARED}" "${PARKED}"
  mkdir -p "${SHARED}"
  # Keep NFS/SMB export path; perms restored after restore via data-root-perms.
  chown root:sharedwrite "${SHARED}" 2>/dev/null || chown root:root "${SHARED}"
  chmod 2775 "${SHARED}"
  docker start opencloud
  echo
  echo "Parked shared content -> system/opencloud/incoming/shared"
  echo "In the browser (admin): Spaces → New Space → name exactly: shared"
  echo "Members: add faiz and diana (Editor or Manager)."
  echo "Then run: $0 restore"
}

restore() {
  if [[ ! -d "${PARKED}" ]]; then
    echo "skip: no parked content at ${PARKED}"
    exit 0
  fi
  if [[ ! -d "${SHARED}" ]]; then
    echo "refusing: ${SHARED} missing. Create the Space named shared first."
    exit 1
  fi
  if [[ -z "$(space_id "${SHARED}")" ]]; then
    echo "refusing: ${SHARED} has no user.oc.space.id."
    echo "Create Project Space named exactly shared, then retry."
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
  echo "Scanning project space so SMB files show up:"
  docker exec opencloud opencloud posixfs scan /posix/projects/shared || true
  echo
  echo "Re-run data-root-perms.sh to restore household ACLs (xattrs are kept)."
  echo "Immich External Library for shared/photos can scan again."
}

case "$1" in
  park) park ;;
  restore) restore ;;
  status) status ;;
  *) usage ;;
esac
