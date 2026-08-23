# OMV shares: NFS for apps, SMB for people

Docker Desktop bind-mounts of a Windows SMB (or NFS) drive letter go through virtiofs and break pathing. This site’s media/HTPC stacks therefore use **`compose.nfs.yaml`** (Docker NFS volume driver). Exceptions that keep `/config` on a local Docker volume: Home Assistant (catalog `configuration.yaml` bind; NFS file overlays drop) and the Arr stack (SQLite cannot run on NFS). Catalog default remains **`compose.yaml`** (`${DATA_ROOT}` binds) for local disk or a host NFS/SMB mount. Pick one file per stack in ResourceSync; do not merge them.

Windows Explorer keeps using **SMB**. Do not point a `compose.yaml` stack’s `DATA_ROOT` at `Z:`. Core still uses the local uuid path as `DATA_ROOT`.

## 1. Shared folder (once)

Workbench: **Storage → Shared Folders**.

Reuse the existing folder that is the **root of the data filesystem** (relative path `/` on the uuid disk). If you already created that folder for SMB, do not add a second one at `/`.

If it does not exist:

1. Add.
2. Name: `data` (this name becomes the NFSv4 export path `/data`).
3. File system: the uuid data disk (`/srv/dev-disk-by-uuid-…`).
4. Relative path: `/`.
5. Save, then **Apply**.

The shared folder name is the NFS path. If yours is not `data`, set Komodo `NFS_EXPORT` to `/<name>` instead of `/data`.

## 2. NFS for the HTPC (apps)

Workbench: **Services → NFS → Settings**

1. Enable NFS.
2. Enable NFSv4 (and 4.1 / 4.2 if listed). NFSv3 can stay on as a fallback.
3. Save, **Apply**.

Workbench: **Services → NFS → Shares → Create**

| Field | Value |
|---|---|
| Shared folder | the folder from step 1 (`data`) |
| Client | the HTPC LAN IP only (CIDR `/32` is fine) |
| Privilege | Read/Write |
| Extra options | `insecure,no_root_squash,subtree_check` |

`insecure` is required: the Docker engine mounts from a high source port. `no_root_squash` is required: linuxserver images chown as root on first start.

Save, **Apply**. Confirm **System → Network** / host firewall allows TCP **2049** from the HTPC (OMV normally opens this when NFS is enabled).

On Core you can instead run:

```text
sudo HTPC_IP=<HTPC_LAN_IP> bash bootstrap/omv-nfs.sh
```

That script creates the `data` folder if missing, enables NFS, and adds the HTPC export. It does not change SMB.

After apply, Core should show something like:

```text
/export/data  <HTPC_IP>(fsid=…,rw,insecure,no_root_squash,subtree_check)
/export       <HTPC_IP>(ro,fsid=0,…)
```

Komodo (periphery / shared variables):

| Key | Value |
|---|---|
| `NAS_LAN_IP` | Core LAN IPv4 |
| `NFS_EXPORT` | `/data` (or `/<shared-folder-name>`) |

No quotes. Unix path, not `Z:`.

NFSv4 path is `/<share-name>`. NFSv3 path would be `/export/<share-name>` — the catalog uses NFSv4.

## 3. SMB stays for drag-and-drop

Workbench: **Services → SMB/CIFS** — leave enabled.

Keep whatever SMB shares you already use for Finder/Explorer (`shared`, user homes, or the disk root). Privileges there are for **faiz**, **diana**, and anyone mapping a drive. They do not control NFS.

You can unmap `Z:` from Docker Desktop **File sharing** once the NFS volumes work. You do not need to unmap it from Windows Explorer.

SMB privileges still do nothing unless that folder is actually an SMB share. Nested access through a root SMB share is POSIX/ACL (`bootstrap/data-root-perms.sh`).

## 4. Smoke test from the HTPC

PowerShell (Docker Desktop running):

```text
docker volume create --driver local --opt type=nfs --opt o=addr=<NAS_LAN_IP>,nfsvers=4,rw,nolock,hard --opt device=:/data nas-nfs-test
docker run --rm -v nas-nfs-test:/data alpine ls /data/system/periphery /data/shared /data/users
docker volume rm nas-nfs-test
```

You should see those three trees. `system/core` may also list because this export is the disk root and `no_root_squash` makes the engine root. Treat the HTPC as trusted; do not export NFS to the whole LAN.

If `ls` fails with `mount.nfs` / `permission denied`, the usual causes are: NFS not applied, client IP not the HTPC, missing `insecure`, or TCP 2049 blocked.

Then redeploy the periphery app stacks in Komodo so they recreate volumes (old SMB bind mounts are not reused).
