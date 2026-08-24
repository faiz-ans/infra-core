#!/usr/bin/env bash
# Enable OMV NFS for the HTPC: export shared/ and users/ only. Does not modify SMB.
# Run on Core as root (after DATA_ROOT exists):
#   sudo HTPC_IP=192.168.1.111 bash bootstrap/omv-nfs.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
DATA_ROOT="${DATA_ROOT%/}"
HTPC_IP="${HTPC_IP:-}"
# OMV "new object" UUID (same as the workbench Create form).
OMV_NEW_UUID="fa4b1c66-ef79-11e5-87a0-0002b3a176b4"
EXTRA_OPTIONS="${EXTRA_OPTIONS:-insecure,no_root_squash,subtree_check}"

if [[ -z "${HTPC_IP}" ]]; then
  echo "Set HTPC_IP to the HTPC LAN address (the NFS client)."
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

  already=$(omv-rpc -u admin NFS getShareList \
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
' "${SHARE_UUID}" "${HTPC_IP}")

  if [[ -n "${already}" ]]; then
    echo "NFS export of ${SHARE_NAME} for ${HTPC_IP} already exists."
  else
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
  fi
}

# omv-rpc -u admin NFS setSettings '{"enable":true,"versions":["3","4","4.1","4.2"]}'
omv-rpc -u admin NFS setSettings '{"enable":true,"versions":["3","4","4.1","4.2"]}' >/dev/null

ensure_share shared shared
ensure_share users users

# omv-salt deploy run fstab
omv-salt deploy run fstab
# omv-salt deploy run nfs
omv-salt deploy run nfs

echo
echo "NFS_EXPORT=/shared"
echo "NFS_USERS=/users"
echo "Set those and NAS_LAN_IP in Komodo. SMB is unchanged."
echo "Remove any NFS export of a disk-root share (old name: data)."
echo "showmount -e \$(hostname -I | awk '{print \$1}')"
