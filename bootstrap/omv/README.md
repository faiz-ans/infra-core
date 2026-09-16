# OMV shares: NFS for apps, SMB for people

Mantle app stacks consume OMV `shared/` and `users/` via **WSL host NFS mounts** plus kube-play `hostPath`. Do not use the Docker NFS volume driver. `/config` stays a local Podman volume so apps start if Core/NFS is down. Windows Explorer keeps **SMB**. OpenCloud on Core uses local binds.

Do not share `C:` into a container engine VM. NFS is mounted inside Ubuntu WSL (`mantle`).

Windows Explorer keeps using **SMB**. Do not point a stack’s `DATA_ROOT` at `Z:`. Core still uses the local uuid path as `DATA_ROOT`.

Export **`shared/`** and **`users/`** only. Do not export the disk root or `system/` (Authelia, Vaultwarden, Pi-hole, WireGuard). **Client must be the surface host IP only** (`SURFACE_UPSTREAM`) — never a whole LAN `/24` alongside the host (duplicate fsids hang `:/shared`).

## 1. Shared folders (once)

On a **greenfield** site, create Shared Folders / NFS **after** OpenCloud publish and `data-root-layout.sh` (so `shared/` is the bound space and layout dirs exist). See `bootstrap/first-run/opencloud.md`.

Workbench: **Storage → Shared Folders**. Add two folders on the uuid data disk if they do not exist:

| Name | Relative path | Becomes NFSv4 path |
|---|---|---|
| `shared` | `shared` | `/shared` |
| `users` | `users` | `/users` |

The shared folder name is the NFS path. If yours differ, set attributes `NFS_SHARED` and `NFS_USERS` (WSL paths) to `/mnt/nas/shared` and `/mnt/nas/users`.

Do not reuse a folder whose relative path is `/` (the old `data` root share). That export can see `system/`.

## 2. NFS for mantle (apps)

Workbench: **Services → NFS → Settings**

1. Enable NFS.
2. Enable NFSv4 (and 4.1 / 4.2 if listed). NFSv3 can stay on as a fallback.
3. Save, **Apply**.

Workbench: **Services → NFS → Shares → Create** — once per folder above.

| Field | Value |
|---|---|
| Shared folder | `shared`, then `users` |
| Client | the surface LAN IP (`SURFACE_UPSTREAM`) only — not a `/24` |
| Privilege | Read/Write |
| Extra options | `no_root_squash,subtree_check` (`insecure` is optional; WSL root mounts use a reserved source port) |

`no_root_squash` is required: linuxserver images chown as root on first start.

Remove any NFS export of the old `data` (disk root) share.

Save, **Apply**. Confirm **System → Network** / host firewall allows TCP **2049** from surface (OMV normally opens this when NFS is enabled).

On Core you can instead run:

```text
sudo HTPC_IP=<SURFACE_UPSTREAM> bash bootstrap/omv/omv-nfs.sh
```

That script creates the `shared` and `users` folders if missing, points ShareMgmt at the current `DATA_ROOT` mntent, enables NFS, exports **only** the surface IP (removes overlapping subnet clients), repairs a hollow `/export/shared` bind if needed, and restarts NFS. It does not change SMB.

After apply, Core should show something like:

```text
/export/shared  <SURFACE_UPSTREAM>(fsid=…,rw,no_root_squash,subtree_check)
/export/users   <SURFACE_UPSTREAM>(fsid=…,rw,no_root_squash,subtree_check)
```

One client line per path. Verify locally: `ls /export/shared/media /export/shared/photos` must list content (not an empty export dir).

Attributes:

| Key | Value |
|---|---|
| `NAS_LAN_IP` | Core LAN IPv4 |
| `NFS_SHARED` | `/mnt/nas/shared` |
| `NFS_USERS` | `/mnt/nas/users` |

No quotes. Unix path, not `Z:`.

NFSv4 path is `/<share-name>`. NFSv3 path would be `/export/<share-name>` — the catalog uses NFSv4.

## 3. SMB stays for drag-and-drop

Workbench: **Services → SMB/CIFS** — leave enabled.

Keep whatever SMB shares you already use for Explorer (`shared`, user homes, or the disk root). Privileges there are for **faiz**, **diana**, and anyone mapping a drive. They do not control NFS.

You do not need a `Z:` mapping for apps. Explorer SMB can stay.

SMB privileges still do nothing unless that folder is actually an SMB share. Nested access through a root SMB share is POSIX/ACL (`bootstrap/data-root/data-root-perms.sh`).

## 4. Smoke test from mantle

On mantle (Ubuntu WSL), as root:

```text
sudo mkdir -p /mnt/nas/shared /mnt/nas/users
sudo mount -t nfs -o nfsvers=4 ${NAS_LAN_IP}:/shared /mnt/nas/shared
sudo mount -t nfs -o nfsvers=4 ${NAS_LAN_IP}:/users /mnt/nas/users
ls /mnt/nas/shared/media /mnt/nas/shared/downloads /mnt/nas/shared/files /mnt/nas/shared/photos /mnt/nas/shared/cameras
ls /mnt/nas/users
```

You should see media/downloads/files/photos/cameras and the user homes. You should not see `system/`. If `cameras` is missing, run `bootstrap/data-root/data-root-perms.sh` on Core.

Persist in `/etc/fstab`. If `ls` hangs: `wsl --shutdown` → on Core re-run `omv-nfs.sh` and confirm `/export/shared/media` is not empty → retry.

If `ls` fails with `mount.nfs` / `permission denied`, the usual causes are: NFS not applied, client IP not `SURFACE_UPSTREAM`, or TCP 2049 blocked.

Then apply `[Hosts.mantle]` in Materia (bootstrap role first).

## 5. If you previously exported the disk root

Remove the old `data` (relative path `/`) NFS share. Unmount WSL paths that still use `:/data/...`, then remount `: /shared` and `:/users`.

## 6. UPS (CyberPower ST625U)

USB HID NUT on Core, low-battery shutdown: `bootstrap/omv/omv-nut.md`. Homepage live widget: `bootstrap/first-run/peanut.md`.

```text
sudo bash bootstrap/omv/omv-nut.sh
```
