#!/usr/bin/env bash
# Personal space is users/<name>/files (not the whole home).
#
# CreateStorageSpace refuses a path that already exists. Login creates
# users/<name>/files with xattrs. photos/ is a sibling Project Space
# (opencloud-adopt-photos.sh), not a folder inside Personal.
#
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-homes.sh park
#   # log in as each household user
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-homes.sh restore
#
# Existing site (space id still on the home root): park, then the same login+restore.
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=data-root-defaults.sh
source "${SCRIPT_DIR}/data-root-defaults.sh"

USERS="${DATA_ROOT}/users"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"

usage() {
  echo "Usage: $0 park|restore|status"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

status() {
  echo "users/: ${USERS}"
  if [[ ! -d "${USERS}" ]]; then
    echo "missing"
    return
  fi
  local u home files sid_home sid_files
  for u in "${HOUSEHOLD[@]}"; do
    home="${USERS}/${u}"
    files="${home}/files"
    if [[ ! -d "${home}" ]]; then
      echo "  ${u}: no home"
      continue
    fi
    sid_home="$(space_id "${home}")"
    sid_files="$(space_id "${files}")"
    if [[ -n "${sid_files}" ]]; then
      echo "  ${u}/files: space id ${sid_files}"
    elif [[ -n "${sid_home}" ]]; then
      echo "  ${u}: OLD space id on home (park → login → restore)"
    else
      echo "  ${u}: no user.oc.space.id"
    fi
  done
  echo "incoming/: ${INCOMING}"
  if [[ -d "${INCOMING}" ]]; then
    local d name
    for d in "${INCOMING}"/*; do
      [[ -d "${d}" ]] || continue
      name="$(basename "${d}")"
      echo "  parked: ${name}"
    done
  fi
}

park() {
  docker stop opencloud
  mkdir -p "${INCOMING}"
  local u src dst files
  for u in "${HOUSEHOLD[@]}"; do
    src="${USERS}/${u}"
    dst="${INCOMING}/${u}"
    files="${src}/files"
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no home)"
      continue
    fi
    if [[ -n "$(space_id "${files}")" ]]; then
      echo "skip ${u} (personal already at files/)"
      continue
    fi
    if [[ -e "${dst}" ]]; then
      echo "refusing: ${dst} already exists"
      exit 1
    fi
    mv "${src}" "${dst}"
    echo "parked ${u} -> system/opencloud/incoming/${u}"
  done
  docker start opencloud
  echo
  echo "In the browser: log in as admin, then as each household user."
  echo "Personal should be users/<name>/files. Then run: $0 restore"
}

restore() {
  docker stop opencloud
  local u src home files item name dest
  for u in "${HOUSEHOLD[@]}"; do
    src="${INCOMING}/${u}"
    if [[ ! -d "${src}" && -d "${USERS}/${u}.__oc_incoming" ]]; then
      src="${USERS}/${u}.__oc_incoming"
    fi
    home="${USERS}/${u}"
    files="${home}/files"
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no parked home)"
      continue
    fi
    if [[ ! -d "${files}" ]]; then
      echo "refusing: ${files} missing. Log in as ${u} first so OpenCloud can mkdir the space."
      exit 1
    fi
    if [[ -z "$(space_id "${files}")" ]]; then
      echo "refusing: ${files} has no user.oc.space.id. Log in as ${u} before restore."
      exit 1
    fi
    shopt -s dotglob nullglob
    for item in "${src}"/*; do
      name="$(basename "${item}")"
      if [[ "${name}" == "photos" ]]; then
        dest="${home}/photos"
      elif [[ "${name}" == "files" ]]; then
        dest="${files}"
      else
        dest="${files}/${name}"
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
        mkdir -p "$(dirname "${dest}")"
        mv "${item}" "${dest}"
      fi
    done
    shopt -u dotglob nullglob
    rmdir "${src}"
    echo "restored ${u} (documents → files/, camera roll → photos/ sibling)"
  done
  docker start opencloud
  echo "Scanning personal spaces:"
  docker exec opencloud opencloud posixfs scan /posix/users || true
  echo
  echo "Next: create photos-<user> spaces (opencloud-adopt-photos.sh), then data-root-layout.sh."
}

case "$1" in
  park) park ;;
  restore) restore ;;
  status) status ;;
  *) usage ;;
esac
