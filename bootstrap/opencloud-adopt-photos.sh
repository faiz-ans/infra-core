#!/usr/bin/env bash
# Per-user camera roll: OpenCloud Project Space "photos-<user>" bound onto
# users/<user>/photos. Personal is users/<user>/files (sibling).
#
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-photos.sh park
#   # browser: Spaces → New Space → name exactly photos-<user>; add that user
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-photos.sh publish
#   sudo DATA_ROOT=… bash bootstrap/opencloud-adopt-photos.sh restore
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=data-root-defaults.sh
source "${SCRIPT_DIR}/data-root-defaults.sh"

USERS="${DATA_ROOT}/users"
PROJECTS="${DATA_ROOT}/system/opencloud/projects"
INCOMING="${DATA_ROOT}/system/opencloud/incoming"

usage() {
  echo "Usage: $0 park|publish|restore|status"
  exit 1
}

[[ $# -eq 1 ]] || usage

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

inode() {
  stat -c '%d:%i' "$1"
}

space_dir() {
  echo "${PROJECTS}/photos-$1"
}

photos_dir() {
  echo "${USERS}/$1/photos"
}

parked_dir() {
  echo "${INCOMING}/photos-$1"
}

fstab_tag() {
  echo "opencloud-photos-$1-bind"
}

published() {
  local u=$1 space photos
  space="$(space_dir "${u}")"
  photos="$(photos_dir "${u}")"
  [[ -d "${space}" && -d "${photos}" ]] || return 1
  [[ "$(inode "${photos}")" == "$(inode "${space}")" ]]
}

write_fstab() {
  local u=$1 tag dest space
  tag="$(fstab_tag "${u}")"
  dest="$(photos_dir "${u}")"
  space="$(space_dir "${u}")"
  if grep -q "${tag}" /etc/fstab 2>/dev/null; then
    sed -i "/${tag}/d" /etc/fstab
  fi
  echo "${space} ${dest} none bind 0 0  # ${tag}" >> /etc/fstab
}

status() {
  local u space photos sid
  for u in "${HOUSEHOLD[@]}"; do
    space="$(space_dir "${u}")"
    photos="$(photos_dir "${u}")"
    echo "${u}: space=${space} photos=${photos}"
    if [[ -d "${space}" ]]; then
      sid="$(space_id "${space}")"
      if [[ -n "${sid}" ]]; then
        echo "  space id ${sid}"
      else
        echo "  no user.oc.space.id (create Space named photos-${u})"
      fi
    else
      echo "  projects/photos-${u} missing"
    fi
    if published "${u}"; then
      echo "  publish: OK"
    else
      echo "  publish: NOT bound"
    fi
    if [[ -d "$(parked_dir "${u}")" ]]; then
      echo "  parked: $(parked_dir "${u}")"
    fi
  done
}

park() {
  docker stop opencloud
  mkdir -p "${INCOMING}" "${PROJECTS}"
  chown "${PUID}:${PGID}" "${PROJECTS}" 2>/dev/null || true
  local u src dst
  for u in "${HOUSEHOLD[@]}"; do
    src="$(photos_dir "${u}")"
    dst="$(parked_dir "${u}")"
    if published "${u}"; then
      echo "skip ${u} (already published)"
      continue
    fi
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no photos dir)"
      continue
    fi
    if [[ -e "${dst}" ]]; then
      echo "refusing: ${dst} already exists"
      exit 1
    fi
    mkdir -p "$(dirname "${src}")"
    mv "${src}" "${dst}"
    echo "parked ${u} photos -> system/opencloud/incoming/photos-${u}"
  done
  docker start opencloud
  echo
  echo "Browser: Spaces → New Space → name exactly photos-<user> (photos-faiz, …)."
  echo "Add that user as member. Then: $0 publish && $0 restore"
}

publish() {
  mkdir -p "${PROJECTS}"
  local u space photos
  for u in "${HOUSEHOLD[@]}"; do
    space="$(space_dir "${u}")"
    photos="$(photos_dir "${u}")"
    if [[ ! -d "${space}" ]]; then
      echo "skip ${u}: ${space} missing (create Space named photos-${u})"
      continue
    fi
    if [[ -z "$(space_id "${space}")" ]]; then
      echo "skip ${u}: no space id on ${space}"
      continue
    fi
    if published "${u}"; then
      echo "already published ${u}"
      write_fstab "${u}"
      continue
    fi
    mkdir -p "$(dirname "${photos}")"
    mkdir -p "${photos}"
    if find "${photos}" -mindepth 1 -print -quit 2>/dev/null | grep -q .; then
      echo "refusing: ${photos} is not empty. Run park first."
      exit 1
    fi
    mount --bind "${space}" "${photos}"
    if ! published "${u}"; then
      echo "refusing: bind failed for ${u}"
      exit 1
    fi
    write_fstab "${u}"
    echo "mounted ${space} -> ${photos}"
  done
}

restore() {
  docker stop opencloud
  local u src dest item
  for u in "${HOUSEHOLD[@]}"; do
    src="$(parked_dir "${u}")"
    dest="$(photos_dir "${u}")"
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no parked photos)"
      continue
    fi
    if ! published "${u}"; then
      echo "refusing: ${u} photos not published. Run publish first."
      exit 1
    fi
    shopt -s dotglob nullglob
    for item in "${src}"/*; do
      if [[ -e "${dest}/$(basename "${item}")" && -d "${item}" ]]; then
        find "${item}" -mindepth 1 -maxdepth 1 -exec mv -t "${dest}" {} +
        rmdir "${item}" 2>/dev/null || true
      else
        mv "${item}" "${dest}/"
      fi
    done
    shopt -u dotglob nullglob
    rmdir "${src}"
    echo "restored ${u} photos"
  done
  docker start opencloud
  echo "Scanning photos spaces:"
  docker exec opencloud opencloud posixfs scan /posix/projects || true
}

case "$1" in
  park) park ;;
  publish) publish ;;
  restore) restore ;;
  status) status ;;
  *) usage ;;
esac
