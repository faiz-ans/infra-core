# Move DATA_ROOT from the stand-in USB to the IronWolf

The USB stays mounted until the copy is verified and Komodo `DATA_ROOT` points at the new uuid path. Do **not** re-run `core.sh` (it latches onto the first `/srv/dev-disk-by-uuid-*` that is already mounted).

Komodo Core (`/etc/komodo`) stays on the Pi OS disk. This move is only the OMV data tree: `system/`, `shared/`, `users/`.

`rsync` **must** keep xattrs (`-X`) and ACLs (`-A`). OpenCloud Personal is `user.oc.space.*` on `users/faiz`. Drop those and spaces vanish again.

## 0. Physical

HAT and IronWolf connected, Pi booted. USB data disk still attached.

## 1. Name the two disks

On Core:

```text
lsblk -o NAME,SIZE,MODEL,TRAN,SERIAL,FSTYPE,UUID,MOUNTPOINT
findmnt /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47
```

USB = current `DATA_ROOT` (`TRAN=usb`, already mounted at `/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47`). IronWolf = `TRAN=sata` (or the HAT’s bus), **not** mounted, no ext4 yet.

Set names and do not mix them:

```text
OLD=/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47
# IronWolf whole disk, e.g. /dev/sda — confirm MODEL. Not the USB. Not the OS mmc/nvme.
DISK=/dev/sdX
```

## 2. Partition and format the IronWolf only

This **erases the IronWolf**. It must not be `OLD`.

```text
sudo wipefs -a "${DISK}"
sudo parted -s "${DISK}" mklabel gpt
sudo parted -s "${DISK}" mkpart primary ext4 0% 100%
sudo partprobe "${DISK}"
sleep 2
sudo lsblk "${DISK}"
```

The partition is usually `${DISK}1` (or `${DISK}p1` on some names). Then:

```text
PART=/dev/sdX1
sudo mkfs.ext4 -F -L core-data "${PART}"
sudo blkid "${PART}"
```

Copy the **UUID=** value. New mount will be `/srv/dev-disk-by-uuid-<that-uuid>`.

```text
NEW_UUID=<paste>
NEW=/srv/dev-disk-by-uuid-${NEW_UUID}
```

ext4 includes `user_xattr` by default. Confirm:

```text
sudo tune2fs -l "${PART}" | grep -i 'Default mount options'
```

You want `user_xattr` listed (or empty defaults — Linux still mounts ext4 with user xattrs).

## 3. Register the filesystem with OMV, then mount

Do **not** write a plain `/etc/fstab` UUID line first. OMV hides disks that are already mounted that way.

```text
sudo mkdir -p "${NEW}"
sudo omv-rpc -u admin FileSystemMgmt setMountPoint "{\"id\":\"${NEW_UUID}\",\"usagewarnthreshold\":85}"
sudo omv-salt deploy run fstab
findmnt -n "${NEW}"
```

If `findmnt` shows nothing:

```text
sudo mount "${NEW}"
findmnt -n "${NEW}"
```

Workbench **Storage → File Systems** should list both the USB and the IronWolf, both mounted. If setMountPoint failed, use the Workbench Mount button on the new ext4 (still better than a handmade fstab line).

Both `OLD` and `NEW` must be mounted before the copy.

## 4. Stop writers

Komodo UI stays up. Stop stacks that bind `DATA_ROOT` (not Caddy, not Komodo):

```text
sudo docker stop opencloud vaultwarden gitea authelia pihole wireguard \
  jotty linkding rustdesk bytestash glances homepage
```

If a name is missing, skip it. On the HTPC, pause Immich/Frigate/Jellyfin/Arr/qBit if they are up so NFS is idle.

## 5. Copy the tree

Trailing slashes matter.

```text
sudo rsync -aAXH --numeric-ids --info=progress2 "${OLD}/" "${NEW}/"
```

`-a` permissions/times, `-A` ACLs, `-X` xattrs, `-H` hard links.

When it finishes:

```text
sudo du -sh "${OLD}" "${NEW}"
sudo getfattr -d "${OLD}/users/faiz"
sudo getfattr -d "${NEW}/users/faiz"
sudo ls -la "${NEW}/system" "${NEW}/shared" "${NEW}/users"
```

New `users/faiz` must still show `user.oc.space.id`. If it does not, the copy dropped xattrs — do not switch `DATA_ROOT`; fix `rsync` and copy again.

## 6. Point OMV shares at the IronWolf

Workbench **Storage → Shared Folders**: edit **`shared`** and **`users`**. Change the filesystem/device from the USB uuid disk to the IronWolf uuid disk. Keep relative paths `shared` and `users`. Save, **Apply**.

NFS (`/shared`, `/users`) and SMB keep the same names. Confirm **Services → NFS** still exports those two folders to the HTPC IP with `insecure,no_root_squash,subtree_check`.

Optional check:

```text
sudo exportfs -v
```

## 7. Switch Komodo `DATA_ROOT`

Komodo → **Settings → Variables** (or the Core secrets file): set

```text
DATA_ROOT=/srv/dev-disk-by-uuid-<NEW_UUID>
```

No trailing slash. Then **Redeploy** every Core stack that mounts it:

`gitea`, `authelia`, `pihole`, `wireguard`, `homepage`, `opencloud`, `vaultwarden`, `jotty`, `linkding`, `rustdesk`, `bytestash`, `glances`.

Leave `restic` off. Redeploy **caddy** only if something else is wrong; it does not use `DATA_ROOT`.

On Core:

```text
sudo docker inspect opencloud --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

You want `${NEW}/system/opencloud/...` and `${NEW}/users` → `/posix/users`, not the old USB uuid.

Then:

```text
sudo DATA_ROOT="${NEW}" bash /path/to/bootstrap/data-root-perms.sh
```

Use the catalog copy of that script (not a stale one in `~`).

## 8. Prove it before unplugging the USB

```text
docker ps --format 'table {{.Names}}\t{{.Status}}'
sudo getfattr -d "${NEW}/users/faiz" | grep space
```

Browser: `https://cloud.home.lan` as **faiz** — Personal still lists. Vaultwarden / Gitea / Authelia still log in.

HTPC (if NFS stacks are up): Explorer/SMB and a docker NFS `ls` of `/shared` still work (`bootstrap/omv-nfs.md` smoke test).

## 9. Unplug the USB only after that

```text
sudo docker stop opencloud vaultwarden gitea authelia pihole wireguard \
  jotty linkding rustdesk bytestash glances homepage
sudo umount "${OLD}"
```

Workbench: unmount/wipe the USB filesystem if OMV still lists it. Physically remove the USB.

Start stacks again (or Komodo Redeploy). Confirm OpenCloud once more.

Keep the USB intact (unmounted) for a day if you want a rollback copy. After that it is spare.

## If something fails

| Symptom | What to do |
|---|---|
| `setMountPoint` / disk missing in OMV | Disk was mounted via a plain fstab line first. Unmount, remove that line, then setMountPoint / Workbench Mount. |
| `getfattr` empty on `${NEW}/users/faiz` | Recopy with `-aAXH`. Do not change `DATA_ROOT` yet. |
| OpenCloud blank after switch | Inspect mounts: still on `OLD` uuid means Komodo `DATA_ROOT` or Redeploy did not apply. |
| NFS `permission denied` from HTPC | Shared folders still on the USB mntent. Edit `shared`/`users` to the IronWolf, Apply NFS. |
| Pi-hole / Authelia unhappy | Those bind `${DATA_ROOT}/system/...`. Redeploy those stacks after the variable change. |
