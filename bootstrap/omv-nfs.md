# OMV shares: NFS for apps, SMB for people

Docker Desktop bind-mounts of a Windows SMB (or NFS) drive letter go through virtiofs and break pathing. This site’s media/HTPC stacks therefore use **`compose.nfs.yaml`** (Docker NFS volume driver). Those stacks keep `/config` on a local Docker volume so the apps can start if Core/NFS is down (Home Assistant also needs that so `ensure-http` can write `trusted_proxies`). Media, downloads, and Immich photo trees stay on NFS. OpenCloud on Core uses local binds of `users/` and `shared/`. Catalog default remains **`compose.yaml`** (`${DATA_ROOT}` binds) for local disk or a host NFS/SMB mount. Pick one file per stack in ResourceSync; do not merge them.

Windows Explorer keeps using **SMB**. Do not point a `compose.yaml` stack’s `DATA_ROOT` at `Z:`. Core still uses the local uuid path as `DATA_ROOT`.

Export **`shared/`** and **`users/`** only. Do not export the disk root or `system/` (Authelia, Vaultwarden, Pi-hole, WireGuard).

## 1. Shared folders (once)

Workbench: **Storage → Shared Folders**. Add two folders on the uuid data disk if they do not exist:

| Name | Relative path | Becomes NFSv4 path |
|---|---|---|
| `shared` | `shared` | `/shared` |
| `users` | `users` | `/users` |

The shared folder name is the NFS path. If yours differ, set Komodo `NFS_EXPORT` and `NFS_USERS` to `/<name>`.

Do not reuse a folder whose relative path is `/` (the old `data` root share). That export can see `system/`.

## 2. NFS for the HTPC (apps)

Workbench: **Services → NFS → Settings**

1. Enable NFS.
2. Enable NFSv4 (and 4.1 / 4.2 if listed). NFSv3 can stay on as a fallback.
3. Save, **Apply**.

Workbench: **Services → NFS → Shares → Create** — once per folder above.

| Field | Value |
|---|---|
| Shared folder | `shared`, then `users` |
| Client | the HTPC LAN IP only (CIDR `/32` is fine) |
| Privilege | Read/Write |
| Extra options | `insecure,no_root_squash,subtree_check` |

`insecure` is required: the Docker engine mounts from a high source port. `no_root_squash` is required: linuxserver images chown as root on first start.

Remove any NFS export of the old `data` (disk root) share.

Save, **Apply**. Confirm **System → Network** / host firewall allows TCP **2049** from the HTPC (OMV normally opens this when NFS is enabled).

On Core you can instead run:

```text
sudo HTPC_IP=<HTPC_LAN_IP> bash bootstrap/omv-nfs.sh
```

That script creates the `shared` and `users` folders if missing, enables NFS, and adds the HTPC exports. It does not change SMB.

After apply, Core should show something like:

```text
/export/shared  <HTPC_IP>(fsid=…,rw,insecure,no_root_squash,subtree_check)
/export/users   <HTPC_IP>(fsid=…,rw,insecure,no_root_squash,subtree_check)
```

Komodo (periphery / shared variables):

| Key | Value |
|---|---|
| `NAS_LAN_IP` | Core LAN IPv4 |
| `NFS_EXPORT` | `/shared` |
| `NFS_USERS` | `/users` |

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
docker volume create --driver local --opt type=nfs --opt o=addr=<NAS_LAN_IP>,nfsvers=4,rw,nolock,hard --opt device=:/shared nas-nfs-shared
docker volume create --driver local --opt type=nfs --opt o=addr=<NAS_LAN_IP>,nfsvers=4,rw,nolock,hard --opt device=:/users nas-nfs-users
docker run --rm -v nas-nfs-shared:/shared alpine ls /shared/media /shared/downloads /shared/files /shared/photos /shared/cameras
docker run --rm -v nas-nfs-users:/users alpine ls /users
docker volume rm nas-nfs-shared nas-nfs-users
```

You should see media/downloads/files/photos/cameras and the user homes. You should not see `system/`.

If `ls` fails with `mount.nfs` / `permission denied`, the usual causes are: NFS not applied, client IP not the HTPC, missing `insecure`, or TCP 2049 blocked.

Then apply `stacks-periphery.toml` in Komodo.

## 5. If you previously exported the disk root

Remove the old `data` (relative path `/`) NFS share. Docker NFS volumes remember `device=:/data/...` until you delete them: stop the HTPC stacks, `docker volume rm` the media/downloads/files/users volumes (not the local `*-config` volumes), then redeploy.
