#!/usr/bin/env bash
# Enable OMV NFS for the HTPC: export shared/ and users/ only. Does not modify SMB.
# Also hardens against failures seen in production:
#   - duplicate NFS clients on the same share (different fsids → Docker Desktop hangs)
#   - empty /export/shared bind after DATA_ROOT / mntent drift (IronWolf migrate)
#   - missing shared/{media,photos,...} dirs
#
# Run on Core as root (after DATA_ROOT exists):
#   sudo HTPC_IP=192.168.1.111 bash bootstrap/omv-nfs.sh
#   sudo HTPC_IP=192.168.1.111 DATA_ROOT=/srv/dev-disk-by-uuid-... bash bootstrap/omv-nfs.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
DATA_ROOT="${DATA_ROOT%/}"
HTPC_IP="${HTPC_IP:-}"
OMV_NEW_UUID="fa4b1c66-ef79-11e5-87a0-0002b3a176b4"
EXTRA_OPTIONS="${EXTRA_OPTIONS:-insecure,no_root_squash,subtree_check}"

if [[ -z "${HTPC_IP}" ]]; then
  echo "Set HTPC_IP to the HTPC LAN address (the NFS client). Do not use a whole /24 here."
  exit 1
fi
if [[ "${HTPC_IP}" == */* ]]; then
  echo "HTPC_IP must be a single host (e.g. 192.168.1.111), not a subnet. Overlapping exports break Docker NFS."
  exit 1
fi
if [[ ! -d "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT not a directory: ${DATA_ROOT}"
  exit 1
fi
if ! command -v omv-rpc >/dev/null 2>&1; then
  echo "omv-rpc not found."
  exit 1
fi

mkdir -p \
  "${DATA_ROOT}/shared/media" \
  "${DATA_ROOT}/shared/downloads" \
  "${DATA_ROOT}/shared/files" \
  "${DATA_ROOT}/shared/photos" \
  "${DATA_ROOT}/shared/cameras" \
  "${DATA_ROOT}/users"

eval "$(python3 - "${DATA_ROOT}" <<'PY'
import json, subprocess, sys

data_root = sys.argv[1].rstrip("/")


def conf(key):
    out = subprocess.check_output(["omv-confdbadm", "read", key], text=True)
    data = json.loads(out)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    return [data] if data else []


mntents = conf("conf.system.filesystem.mountpoint")
mntent = next(
    (m for m in mntents if str(m.get("dir", "")).rstrip("/") == data_root),
    None,
)
if not mntent:
    sys.stderr.write(f"No OMV mountpoint for {data_root}\n")
    sys.exit(1)
print(f"MNTENT_UUID={mntent['uuid']}")
PY
)"

# Point OMV "shared" / "users" folders at this DATA_ROOT mntent (fixes hollow /export after migrate).
python3 - "${DATA_ROOT}" "${MNTENT_UUID}" <<'PY'
import json, subprocess, sys

data_root, mnt_uuid = sys.argv[1].rstrip("/"), sys.argv[2]


def conf(key):
    out = subprocess.check_output(["omv-confdbadm", "read", key], text=True)
    data = json.loads(out)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    return [data] if data else []


def rpc(service, method, params):
    out = subprocess.check_output(
        ["omv-rpc", "-u", "admin", service, method, json.dumps(params)],
        text=True,
    )
    return json.loads(out) if out.strip() else None


for want_name, rel in (("shared", "shared"), ("users", "users")):
    share = None
    for folder in conf("conf.system.sharedfolder"):
        r = str(folder.get("reldirpath", "")).replace("\\", "/").strip("/")
        if folder.get("name") == want_name or r == rel:
            share = folder
            break
    if not share:
        print(f"ShareMgmt '{want_name}' missing (will create via ensure_share).")
        continue
    need = share.get("mntentref") != mnt_uuid or str(share.get("reldirpath", "")).replace("\\", "/").strip("/") != rel
    if not need:
        print(f"ShareMgmt '{want_name}' already on DATA_ROOT mntent.")
        continue
    print(f"Updating ShareMgmt '{want_name}' -> mntent {mnt_uuid}, reldirpath {rel}/")
    rpc("ShareMgmt", "set", {
        "uuid": share["uuid"],
        "name": share.get("name") or want_name,
        "reldirpath": f"{rel}/",
        "comment": share.get("comment") or "HTPC NFS",
        "mntentref": mnt_uuid,
    })
PY

ensure_share() {
  local name="$1"
  local rel="$2"
  eval "$(python3 - "${MNTENT_UUID}" "${name}" "${rel}" <<'PY'
import json, subprocess, sys

mntent_uuid, want_name, rel_want = sys.argv[1], sys.argv[2], sys.argv[3].strip("/")


def conf(key):
    out = subprocess.check_output(["omv-confdbadm", "read", key], text=True)
    data = json.loads(out)
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    return [data] if data else []


share = None
for folder in conf("conf.system.sharedfolder"):
    rel = str(folder.get("reldirpath", "")).replace("\\", "/").strip("/")
    if folder.get("mntentref") == mntent_uuid and rel == rel_want:
        share = folder
        break
    if folder.get("name") == want_name:
        share = folder
        break
if share:
    print(f"SHARE_UUID={share['uuid']}")
    print(f"SHARE_NAME={share['name']}")
else:
    print("SHARE_UUID=")
    print(f"SHARE_NAME={want_name}")
PY
)"
  if [[ -z "${SHARE_UUID}" ]]; then
    echo "Creating shared folder ${name} at ${DATA_ROOT}/${rel}"
    created=$(omv-rpc -u admin ShareMgmt set "$(python3 -c "import json; print(json.dumps({
      'uuid': '${OMV_NEW_UUID}',
      'name': '${name}',
      'reldirpath': '${rel}/',
      'comment': 'HTPC NFS (not system/)',
      'mntentref': '${MNTENT_UUID}',
    }))")")
    SHARE_UUID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['uuid'])" <<<"${created}")
    SHARE_NAME="${name}"
  fi
  echo "Shared folder ${SHARE_NAME} uuid=${SHARE_UUID}"

  # Drop other NFS clients for this share (subnet duplicates with different fsids hang Docker Desktop).
  python3 - "${SHARE_UUID}" "${HTPC_IP}" <<'PY'
import json, subprocess, sys

share_uuid, htpc = sys.argv[1], sys.argv[2]
keep = {htpc, htpc + "/32"}


def rpc(service, method, params=None):
    cmd = ["omv-rpc", "-u", "admin", service, method]
    if params is not None:
        cmd.append(json.dumps(params))
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out) if out.strip() else None


payload = rpc("NFS", "getShareList", {
    "start": 0, "limit": 500, "sortfield": "sharedfoldername", "sortdir": "ASC"
})
rows = payload.get("data", payload if isinstance(payload, list) else [])
kept = False
for row in rows:
    if row.get("sharedfolderref") != share_uuid:
        continue
    client = str(row.get("client", ""))
    if client in keep:
        print(f"KEEP NFS {client}")
        kept = True
        continue
    print(f"DELETE NFS client={client} uuid={row['uuid']} (duplicate/overlap)")
    rpc("NFS", "deleteShare", {"uuid": row["uuid"]})

if not kept:
    print("NEED_CREATE")
else:
    print("HAVE_HTPC")
PY

  if ! omv-rpc -u admin NFS getShareList \
    '{"start":0,"limit":500,"sortfield":"sharedfoldername","sortdir":"ASC"}' \
    | python3 -c '
import json, sys
share_uuid, client = sys.argv[1], sys.argv[2]
payload = json.load(sys.stdin)
rows = payload.get("data", payload if isinstance(payload, list) else [])
want = {client, client + "/32"}
for row in rows:
    if row.get("sharedfolderref") == share_uuid and row.get("client") in want:
        print("yes")
        break
' "${SHARE_UUID}" "${HTPC_IP}" | grep -q yes; then
    echo "Creating NFS export of ${SHARE_NAME} for ${HTPC_IP}"
    omv-rpc -u admin NFS setShare "$(python3 -c "import json; print(json.dumps({
      'uuid': '${OMV_NEW_UUID}',
      'sharedfolderref': '${SHARE_UUID}',
      'mntentref': '${MNTENT_UUID}',
      'client': '${HTPC_IP}',
      'options': 'rw',
      'extraoptions': '${EXTRA_OPTIONS}',
      'comment': 'HTPC Docker NFS',
    }))")" >/dev/null
  else
    echo "NFS export of ${SHARE_NAME} for ${HTPC_IP} already exists."
  fi
}

omv-rpc -u admin NFS setSettings '{"enable":true,"versions":["3","4","4.1","4.2"]}' >/dev/null

ensure_share shared shared
ensure_share users users

omv-salt deploy run fstab
omv-salt deploy run nfs

# If /export/shared is still hollow, bind the real tree (survives until next wrong fstab).
fix_export_bind() {
  local name="$1"
  local src="${DATA_ROOT}/${name}"
  local dst="/export/${name}"
  if [[ ! -d "${src}" ]]; then
    echo "Missing ${src}"
    return 1
  fi
  mkdir -p "${dst}"
  # Hollow = export dir exists but lacks expected children while DATA_ROOT has them
  if [[ "${name}" == "shared" ]]; then
    if [[ -d "${src}/media" ]] && [[ ! -d "${dst}/media" ]]; then
      echo "Repairing hollow ${dst} -> bind ${src}"
      if findmnt "${dst}" >/dev/null 2>&1; then
        umount -l "${dst}" || umount -f "${dst}" || true
      fi
      mount --bind "${src}" "${dst}"
      mount --make-shared "${dst}" 2>/dev/null || true
    fi
  fi
  if [[ ! -e "${dst}" ]] || [[ -z "$(ls -A "${dst}" 2>/dev/null || true)" ]]; then
    if [[ -n "$(ls -A "${src}" 2>/dev/null || true)" ]]; then
      echo "Repairing empty ${dst} -> bind ${src}"
      if findmnt "${dst}" >/dev/null 2>&1; then
        umount -l "${dst}" || umount -f "${dst}" || true
      fi
      mount --bind "${src}" "${dst}"
      mount --make-shared "${dst}" 2>/dev/null || true
    fi
  fi
}

fix_export_bind shared
fix_export_bind users

exportfs -ra 2>/dev/null || exportfs -f || true
systemctl restart nfs-kernel-server 2>/dev/null || systemctl restart nfs-server 2>/dev/null || true

echo
echo "=== /etc/exports (one client per path) ==="
grep -E '^/export' /etc/exports || true
echo
echo "=== verify ==="
ls /export/shared/media /export/shared/photos /export/users 2>&1 | head -30 || true
echo
echo "NFS_EXPORT=/shared"
echo "NFS_USERS=/users"
echo "Set those and NAS_LAN_IP in Komodo. SMB is unchanged."
echo "HTPC smoke test: bootstrap/omv-nfs.md §4 (soft mount first if unsure)."
echo "Remove any NFS export of a disk-root share (old name: data)."
echo "showmount -e \$(hostname -I | awk '{print \$1}')"
