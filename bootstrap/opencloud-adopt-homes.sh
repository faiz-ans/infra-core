#!/usr/bin/env bash
# OpenCloud CreateStorageSpace refuses a path that already exists and does
# not stamp xattrs or the space index. Household users/<name> homes therefore
# never become Personal spaces.
#
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-adopt-homes.sh park
#   # log in as admin, then each household user, in the browser
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-adopt-homes.sh restore
#
# park moves only homes that lack user.oc.space.id. restore merges files back
# into the new space inode (xattrs stay on users/<name>).
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
HOUSEHOLD=(faiz diana)
USERS="${DATA_ROOT}/users"
# Park outside users/: a sibling like faiz.__oc_incoming makes CreateStorageSpace
# fail with node.Xattrs /posix/users/faiz.__oc_incoming.
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
  local d name sid
  for d in "${USERS}"/*; do
    [[ -d "${d}" ]] || continue
    name="$(basename "${d}")"
    sid="$(space_id "${d}")"
    if [[ -n "${sid}" ]]; then
      echo "  ${name}: space id ${sid}"
    else
      echo "  ${name}: no user.oc.space.id"
    fi
  done
  echo "incoming/: ${INCOMING}"
  if [[ -d "${INCOMING}" ]]; then
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
  local u src dst
  for u in "${HOUSEHOLD[@]}"; do
    src="${USERS}/${u}"
    dst="${INCOMING}/${u}"
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no home)"
      continue
    fi
    if [[ -n "$(space_id "${src}")" ]]; then
      echo "skip ${u} (already a space)"
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
  echo "Admin Settings -> Spaces should list Personal. Then run: $0 restore"
}

restore() {
  docker stop opencloud
  local u src dst item
  for u in "${HOUSEHOLD[@]}"; do
    src="${INCOMING}/${u}"
    if [[ ! -d "${src}" && -d "${USERS}/${u}.__oc_incoming" ]]; then
      src="${USERS}/${u}.__oc_incoming"
    fi
    dst="${USERS}/${u}"
    if [[ ! -d "${src}" ]]; then
      echo "skip ${u} (no parked home)"
      continue
    fi
    if [[ ! -d "${dst}" ]]; then
      echo "refusing: ${dst} missing. Log in as ${u} first so OpenCloud can mkdir the space."
      exit 1
    fi
    if [[ -z "$(space_id "${dst}")" ]]; then
      echo "refusing: ${dst} has no user.oc.space.id. Log in as ${u} before restore."
      exit 1
    fi
    shopt -s dotglob nullglob
    for item in "${src}"/*; do
      local name dest
      name="$(basename "${item}")"
      dest="${dst}/${name}"
      if [[ -e "${dest}" ]]; then
        if [[ -d "${item}" && -d "${dest}" ]]; then
          # same-FS merge without replacing the space inode
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
    rmdir "${src}"
    echo "restored ${u}"
  done
  docker start opencloud
  echo "Scanning spaces so files/ and photos/ show up:"
  docker exec opencloud opencloud posixfs scan /posix || true
  echo
  echo "Re-run data-root-perms.sh to restore household ACLs (xattrs are kept)."
  echo "After shared adopt + perms: DATA_ROOT=${DATA_ROOT} bash bootstrap/opencloud-check.sh"
}

case "$1" in
  park) park ;;
  restore) restore ;;
  status) status ;;
  *) usage ;;
esac
