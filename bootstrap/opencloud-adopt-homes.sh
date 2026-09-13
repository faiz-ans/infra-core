#!/usr/bin/env bash
# Personal space is users/<name>/files (not the whole home).
#
# CreateStorageSpace refuses a path that already exists. Login creates
# users/<name>/files with xattrs. photos/ is a sibling Project Space
# (opencloud-adopt-photos.sh), not a folder inside Personal.
#
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-homes.sh park
#   # Authelia as each household user (not OpenCloud local admin)
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-homes.sh restore
#
# If Personal is still the home after a correct template: the user already
# has a space ID (login will not mkdir files/). Run relocate, then restore.
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
  DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"
  HOUSEHOLD=(faiz diana)
  HTPC=periphery
  ADMIN=pilot
  SHARED_GROUP=sharedwrite
  HTPC_GROUP=htpc
fi

USERS="${DATA_ROOT}/users"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"

usage() {
  echo "Usage: $0 park|restore|status|relocate|drop-wrong-login"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

is_oc_meta() {
  [[ "$1" == ".oc-nodes" || "$1" == .oc-* ]]
}

is_skip_name() {
  [[ "$1" == ._* || "$1" == ".DS_Store" || "$1" == "Thumbs.db" || "$1" == "desktop.ini" ]]
}

discard_oc_meta() {
  local dir=$1
  [[ -d "${dir}" ]] || return 0
  find "${dir}" -mindepth 1 -maxdepth 1 -name '.oc-*' -exec rm -rf {} +
}

discard_skip_names() {
  local dir=$1
  [[ -d "${dir}" ]] || return 0
  find "${dir}" -mindepth 1 -maxdepth 1 \( -name '._*' -o -name '.DS_Store' -o -name 'Thumbs.db' -o -name 'desktop.ini' \) -exec rm -rf {} +
}

# Parked original wins over leftover login/partial-restore files. Skip posix
# metadata and macOS AppleDouble (._*).
place_item() {
  local item=$1 dest=$2 name
  name="$(basename "${item}")"
  if is_oc_meta "${name}" || is_skip_name "${name}"; then
    return 0
  fi
  if [[ -e "${dest}" ]]; then
    if [[ -d "${item}" && -d "${dest}" ]]; then
      merge_into "${item}" "${dest}"
      discard_oc_meta "${item}"
      discard_skip_names "${item}"
      rmdir "${item}" 2>/dev/null || {
        echo "could not empty ${item}; leaving parked files"
        exit 1
      }
    elif [[ -f "${item}" && -f "${dest}" ]]; then
      mv -f "${item}" "${dest}"
    else
      echo "refusing: ${dest} exists and is not a mergeable directory"
      exit 1
    fi
  else
    mkdir -p "$(dirname "${dest}")"
    mv "${item}" "${dest}"
  fi
}

merge_into() {
  local src=$1 dest=$2 child name
  mkdir -p "${dest}"
  while IFS= read -r -d '' child; do
    name="$(basename "${child}")"
    place_item "${child}" "${dest}/${name}"
  done < <(find "${src}" -mindepth 1 -maxdepth 1 -print0)
}

live_template() {
  docker exec opencloud printenv STORAGE_USERS_POSIX_PERSONAL_SPACE_PATH_TEMPLATE 2>/dev/null || true
}

status() {
  echo "users/: ${USERS}"
  echo "template: $(live_template || echo unknown)"
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
      echo "  ${u}: space id on HOME. Run $0 relocate (login will not move it)."
    else
      echo "  ${u}: no user.oc.space.id on home or files/"
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
  echo "Komodo must have Redeployed opencloud so the template is users/<user>/files."
  echo "Check: docker exec opencloud printenv STORAGE_USERS_POSIX_PERSONAL_SPACE_PATH_TEMPLATE"
  echo "Then Authelia as faiz, then diana (not OpenCloud local admin)."
  echo "If $0 status still shows space id on HOME, run $0 relocate, then restore."
}

drop_wrong_login() {
  docker stop opencloud
  local u home files stamp
  stamp="$(date +%Y%m%dT%H%M%S)"
  for u in "${HOUSEHOLD[@]}"; do
    home="${USERS}/${u}"
    files="${home}/files"
    if [[ ! -d "${INCOMING}/${u}" ]]; then
      echo "skip ${u} (no parked original at incoming/${u})"
      continue
    fi
    if [[ ! -d "${home}" ]]; then
      echo "skip ${u} (no new home)"
      continue
    fi
    if [[ -n "$(space_id "${files}")" ]]; then
      echo "skip ${u} (files/ already has space id — run restore)"
      continue
    fi
    mv "${home}" "${INCOMING}/${u}.wrong-login-${stamp}"
    echo "moved users/${u} -> incoming/${u}.wrong-login-${stamp}"
  done
  docker start opencloud
  echo
  echo "drop-wrong-login only helps before the first Personal space exists."
  echo "If status still shows space id on HOME after a later login, run $0 relocate."
}

# Keep the existing Personal space ID; move the space root inode from
# users/<u> down to users/<u>/files. Login cannot do this: the template is
# only used when CreateStorageSpace runs, and faiz/diana already have spaces.
#
# The old home often already contains a files/ folder. After the move that
# becomes users/<u>/files/files. Do not flatten .oc-nodes onto the space root.
flatten_nested_files() {
  local files=$1 nested item name dest
  nested="${files}/files"
  if [[ ! -d "${nested}" || -n "$(space_id "${nested}")" ]]; then
    return 0
  fi
  shopt -s dotglob nullglob
  for item in "${nested}"/*; do
    name="$(basename "${item}")"
    dest="${files}/${name}"
    if [[ -e "${dest}" ]]; then
      continue
    fi
    mv "${item}" "${dest}"
  done
  shopt -u dotglob nullglob
  rmdir "${nested}" 2>/dev/null || true
}

relocate() {
  docker stop opencloud
  trap 'docker start opencloud >/dev/null 2>&1 || true' EXIT
  mkdir -p "${INCOMING}"
  local u home files staging stamp
  stamp="$(date +%Y%m%dT%H%M%S)"
  for u in "${HOUSEHOLD[@]}"; do
    home="${USERS}/${u}"
    files="${home}/files"
    if [[ ! -d "${home}" ]]; then
      echo "skip ${u} (no home)"
      continue
    fi
    if [[ -n "$(space_id "${files}")" ]]; then
      flatten_nested_files "${files}"
      echo "skip ${u} (personal already at files/)"
      continue
    fi
    if [[ -z "$(space_id "${home}")" ]]; then
      echo "skip ${u} (no space id on home — Authelia login first)"
      continue
    fi
    staging="${INCOMING}/${u}.relocate-${stamp}"
    if [[ -e "${staging}" ]]; then
      echo "refusing: ${staging} already exists"
      exit 1
    fi
    mv "${home}" "${staging}"
    mkdir -p "${home}"
    chown "${PUID}:${PGID}" "${home}"
    mv "${staging}" "${files}"
    flatten_nested_files "${files}"
    echo "relocated ${u}: space id $(space_id "${files}") now on users/${u}/files"
  done
  trap - EXIT
  docker start opencloud
  echo "Scanning personal spaces:"
  docker exec opencloud sh -c 'for d in /posix/users/*/files; do opencloud posixfs scan "$d" || true; done'
  echo
  echo "Check: $0 status  (want space id on users/<u>/files)."
  echo "Then: $0 restore"
}

restore() {
  docker stop opencloud
  trap 'docker start opencloud >/dev/null 2>&1 || true' EXIT
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
      echo "refusing: ${files} missing. Log in as ${u} after Redeploy so OpenCloud mkdir's the space."
      exit 1
    fi
    if [[ -z "$(space_id "${files}")" ]]; then
      echo "refusing: ${files} has no user.oc.space.id."
      echo "Personal is still the home. The path template is not used for an"
      echo "existing space — login keeps recreating users/${u}, not files/."
      echo "  home  xattr: $(space_id "${home}" || echo none)"
      echo "  files xattr: none"
      echo "  template:    $(live_template || echo unknown)"
      echo "Do not restore. Do not drop-wrong-login. Run: $0 relocate"
      exit 1
    fi
    shopt -s dotglob nullglob
    for item in "${src}"/*; do
      name="$(basename "${item}")"
      if is_oc_meta "${name}" || is_skip_name "${name}"; then
        continue
      fi
      if [[ "${name}" == "photos" ]]; then
        dest="${home}/photos"
      elif [[ "${name}" == "files" ]]; then
        dest="${files}"
      else
        dest="${files}/${name}"
      fi
      place_item "${item}" "${dest}"
    done
    shopt -u dotglob nullglob
    discard_oc_meta "${src}"
    discard_skip_names "${src}"
    rmdir "${src}"
    echo "restored ${u} (documents → files/, camera roll → photos/ sibling)"
  done
  trap - EXIT
  docker start opencloud
  echo "Scanning personal spaces:"
  docker exec opencloud sh -c 'for d in /posix/users/*/files; do opencloud posixfs scan "$d" || true; done'
  echo
  echo "Next: create photos-<user> spaces (opencloud-adopt-photos.sh), then data-root-layout.sh."
}

case "$1" in
  park) park ;;
  restore) restore ;;
  status) status ;;
  relocate) relocate ;;
  drop-wrong-login) drop_wrong_login ;;
  *) usage ;;
esac
