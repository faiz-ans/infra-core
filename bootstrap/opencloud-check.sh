#!/usr/bin/env bash
# Read-only readiness check for OpenCloud on Core.
#   sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/opencloud-check.sh
#
# Exit 0 only if all required checks pass. Does not mount, chown, or deploy.
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
HOUSEHOLD=(faiz diana)
SHARED="${DATA_ROOT}/shared"
PROJECTS="${DATA_ROOT}/system/opencloud/projects"
SPACE="${PROJECTS}/shared"
RADICALE="${DATA_ROOT}/system/opencloud/radicale"
USERS="${DATA_ROOT}/users"

FAILS=0
pass() { echo "OK  $*"; }
fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }
warn() { echo "WARN $*"; }

space_id() {
  getfattr -n user.oc.space.id --only-values "$1" 2>/dev/null || true
}

published() {
  [[ -d "${SPACE}" && -d "${SHARED}" ]] || return 1
  [[ "$(stat -c '%d:%i' "${SHARED}")" == "$(stat -c '%d:%i' "${SPACE}")" ]]
}

echo "DATA_ROOT=${DATA_ROOT}"
echo

# --- containers ---
if docker inspect -f '{{.State.Status}}' opencloud 2>/dev/null | grep -qx running; then
  pass "container opencloud running"
else
  fail "container opencloud not running"
fi
if docker inspect -f '{{.State.Status}}' radicale 2>/dev/null | grep -qx running; then
  pass "container radicale running"
else
  fail "container radicale not running"
fi
if docker inspect -f '{{.State.Status}}' collabora 2>/dev/null | grep -qx running; then
  pass "container collabora running"
  if docker inspect -f '{{.State.Status}}' collabora-ca 2>/dev/null | grep -qx running; then
    pass "container collabora-ca running"
  else
    fail "container collabora-ca not running (CA/proof_key sidecar)"
  fi
else
  warn "container collabora not running (skip if office not deployed yet)"
fi

# --- proof disable ---
if docker inspect opencloud >/dev/null 2>&1; then
  if docker exec opencloud /bin/sh -c 'printenv COLLABORATION_APP_PROOF_DISABLE' 2>/dev/null | grep -qx true; then
    pass "COLLABORATION_APP_PROOF_DISABLE=true"
  else
    # env may only be on the process; try compose-style inspect
    if docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' opencloud 2>/dev/null \
      | grep -qx 'COLLABORATION_APP_PROOF_DISABLE=true'; then
      pass "COLLABORATION_APP_PROOF_DISABLE=true"
    else
      fail "COLLABORATION_APP_PROOF_DISABLE not true (Collabora CheckFileInfo will 500)"
    fi
  fi
fi

# --- personal spaces ---
for u in "${HOUSEHOLD[@]}"; do
  home="${USERS}/${u}"
  parked="${DATA_ROOT}/system/opencloud/incoming/${u}"
  if [[ -d "${parked}" ]]; then
    fail "users/${u}: still parked at ${parked} (login as ${u}, then adopt-homes restore)"
    continue
  fi
  if [[ ! -d "${home}" ]]; then
    fail "users/${u}: missing (login as ${u} after park, or create home)"
    continue
  fi
  sid="$(space_id "${home}")"
  if [[ -n "${sid}" ]]; then
    pass "users/${u}: space id ${sid}"
  else
    fail "users/${u}: no user.oc.space.id (adopt-homes park → login → restore)"
  fi
done

# --- shared project space ---
if [[ ! -d "${SPACE}" ]]; then
  fail "projects/shared missing (create Space named exactly shared)"
elif [[ -z "$(space_id "${SPACE}")" ]]; then
  fail "projects/shared has no user.oc.space.id"
else
  pass "projects/shared: space id $(space_id "${SPACE}")"
fi

if published; then
  pass "shared bind: same inode as projects/shared ($(stat -c '%d:%i' "${SHARED}"))"
else
  fail "shared bind: NOT same inode (run opencloud-adopt-shared.sh publish)"
  if [[ -d "${SHARED}" && -d "${SPACE}" ]]; then
    echo "     shared=$(stat -c '%d:%i' "${SHARED}") space=$(stat -c '%d:%i' "${SPACE}")"
  fi
fi

if [[ -d "${DATA_ROOT}/system/opencloud/incoming/shared" ]]; then
  fail "shared content still parked at system/opencloud/incoming/shared (run restore after publish)"
fi

# --- sticky / layout sample ---
if [[ -d "${SHARED}" ]]; then
  if stat -c '%A' "${SHARED}" | grep -q '[tT]'; then
    pass "shared/: sticky bit set ($(stat -c '%A' "${SHARED}"))"
  else
    fail "shared/: sticky bit missing (re-run data-root-perms.sh)"
  fi
  if [[ -d "${SHARED}/photos" ]]; then
    own="$(stat -c '%U' "${SHARED}/photos")"
    if [[ "${own}" == root ]]; then
      pass "shared/photos: owner root"
    else
      fail "shared/photos: owner ${own} (want root; re-run data-root-perms.sh)"
    fi
  fi
fi

for u in "${HOUSEHOLD[@]}"; do
  files="${USERS}/${u}/files"
  [[ -d "${files}" ]] || continue
  own="$(stat -c '%U' "${files}")"
  if [[ "${own}" == root ]]; then
    pass "users/${u}/files: owner root"
  else
    fail "users/${u}/files: owner ${own} (want root; re-run data-root-perms.sh)"
  fi
done

# --- radicale ownership ---
if [[ -d "${RADICALE}" ]]; then
  own="$(stat -c '%u:%g' "${RADICALE}")"
  if [[ "${own}" == "${PUID}:${PGID}" ]]; then
    pass "radicale data owned by ${PUID}:${PGID}"
  else
    fail "radicale data owned by ${own} (want ${PUID}:${PGID}; chown or data-root-perms)"
  fi
else
  fail "radicale data dir missing: ${RADICALE}"
fi

# --- projects parent writable by PUID ---
if [[ -d "${PROJECTS}" ]]; then
  own="$(stat -c '%u:%g' "${PROJECTS}")"
  if [[ "${own}" == "${PUID}:${PGID}" ]]; then
    pass "projects/ owned by ${PUID}:${PGID}"
  else
    # After shared publish, protect may leave projects as pilot still — OK if PUID can write
    if [[ -O "${PROJECTS}" ]] || [[ "$(stat -c '%u' "${PROJECTS}")" == "${PUID}" ]]; then
      pass "projects/ uid $(stat -c '%u' "${PROJECTS}") (PUID ${PUID})"
    else
      warn "projects/ owned by ${own} (OpenCloud may need chown ${PUID}:${PGID} on parent)"
    fi
  fi
fi

echo
if [[ "${FAILS}" -eq 0 ]]; then
  echo "All required checks passed."
  exit 0
fi
echo "${FAILS} check(s) failed. See bootstrap/opencloud.md happy path."
exit 1
