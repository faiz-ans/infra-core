# Lab history only — not Layer 0.

# Move DATA_ROOT from the stand-in USB to the IronWolf

This document is **not** the happy path for a new site. Default deploy remounts an existing ext4 data disk or formats an empty one (`bootstrap/SITE-DEPLOY.md`). Use this file only if you still have the USB stand-in from the original lab.

The USB stays mounted until the copy is verified and `DATA_ROOT` in `/etc/infra-core/site.env` points at the new uuid path. Do **not** re-run `core.sh` (it latches onto the first `/srv/dev-disk-by-uuid-*` that is already mounted).

Site env (`/etc/infra-core`) stays on the Pi OS disk. This move is only the OMV data tree: `system/`, `shared/`, `users/`.

`rsync` **must** keep xattrs (`-X`) and ACLs (`-A`). OpenCloud Personal is `user.oc.space.*` on `users/faiz`. Drop those and spaces vanish again.

## 0. Physical

HAT and IronWolf connected, Pi booted. USB data disk still attached.

Copies (Explorer SMB, WSL NFS) are faster on Ethernet. Pin `SURFACE_UPSTREAM` with `bootstrap/surface/surface-lan-static.ps1`.

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

Cockpit / systemd stays up. Stop stacks that bind `DATA_ROOT` (not Caddy):

```text
sudo podman stop opencloud vaultwarden authelia pihole wireguard \
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

NFS (`/shared`, `/users`) and SMB keep the same names. Re-run so ShareMgmt/`/export` track the IronWolf (avoids a hollow `/export/shared`):

```text
sudo HTPC_IP=<HTPC_LAN_IP> DATA_ROOT=/srv/dev-disk-by-uuid-<NEW_UUID> bash bootstrap/omv/omv-nfs.sh
ls /export/shared/media /export/shared/photos
```

Confirm **Services → NFS** still exports those two folders to the **HTPC host IP only** (not a LAN `/24`) with `insecure,no_root_squash,subtree_check`.

Optional check:

```text
sudo exportfs -v
```

## 7. Switch attribute `DATA_ROOT`

Quadlets read `DATA_ROOT` from `/etc/infra-core/site.env` (and sops attributes). Changing only a running container env does **not** rewrite that file — a restart keeps the old uuid mounts.

On Core (as root), set **site.env**, answers cache, and encrypted attributes, then re-apply:

```text
NEW=/srv/dev-disk-by-uuid-<NEW_UUID>
sudo grep -E '^DATA_ROOT' /etc/infra-core/site.env /etc/infra-core/bootstrap-answers.env
sudo sed -i "s|^DATA_ROOT=.*|DATA_ROOT=${NEW}|" /etc/infra-core/site.env
sudo sed -i "s|^DATA_ROOT=.*|DATA_ROOT='${NEW}'|" /etc/infra-core/bootstrap-answers.env
sudo grep -E '^DATA_ROOT' /etc/infra-core/site.env /etc/infra-core/bootstrap-answers.env
# Re-encrypt attributes/core.age on-box, then:
systemctl --machine=pilot@ --user daemon-reload
# or wait for the Materia user timer
```

No trailing slash. Then re-apply every Core stack that mounts it (Restart is not enough):

`authelia`, `pihole`, `wireguard`, `homepage`, `opencloud`, `vaultwarden`, `jotty`, `linkding`, `rustdesk`, `bytestash`, `glances`.

Leave `restic` off until this copy is done and the surface USB is `BACKUP_DRIVE` ([`bootstrap/first-run/restic.md`](../first-run/restic.md)). Re-apply **caddy** only if something else is wrong; it does not use `DATA_ROOT`.

On Core:

```text
sudo podman inspect opencloud --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

You want `${NEW}/system/opencloud/...` and `${NEW}/users` → `/posix/users`, not the old USB uuid.

If mounts are still the USB path: `grep DATA_ROOT /etc/infra-core/site.env` must show `${NEW}`, then re-apply OpenCloud again. Hits under `components/opencloud/` in the clone are only defaults — they do not set live mounts.

Then re-bind OpenCloud spaces. **`rsync` does not preserve bind mounts** — on `${NEW}` you get two separate trees (`shared/files` vs `projects/shared`, and `users/<u>/photos` vs `projects/photos-<u>`). Spaces already have `user.oc.space.id`; do **not** park whole `shared/` (that moves media). Merge into the space dirs, empty the household paths, then publish:

```text
CATALOG=/home/pilot/infra-core
# Optional sanity: sizes should be similar (duplicates from the old binds)
sudo du -sh "${NEW}/shared/files" "${NEW}/system/opencloud/projects/shared"
sudo du -sh "${NEW}/users/faiz/photos" "${NEW}/system/opencloud/projects/photos-faiz"
sudo du -sh "${NEW}/users/diana/photos" "${NEW}/system/opencloud/projects/photos-diana"

sudo podman stop opencloud
sudo rsync -aAXH --numeric-ids "${NEW}/shared/files/" "${NEW}/system/opencloud/projects/shared/"
sudo find "${NEW}/shared/files" -mindepth 1 -delete
sudo DATA_ROOT="${NEW}" bash "${CATALOG}/bootstrap/opencloud/opencloud-adopt-shared.sh" publish

sudo rsync -aAXH --numeric-ids "${NEW}/users/faiz/photos/" "${NEW}/system/opencloud/projects/photos-faiz/"
sudo rsync -aAXH --numeric-ids "${NEW}/users/diana/photos/" "${NEW}/system/opencloud/projects/photos-diana/"
sudo find "${NEW}/users/faiz/photos" -mindepth 1 -delete
sudo find "${NEW}/users/diana/photos" -mindepth 1 -delete
sudo DATA_ROOT="${NEW}" bash "${CATALOG}/bootstrap/opencloud/opencloud-adopt-photos.sh" publish
sudo podman start opencloud

sudo DATA_ROOT="${NEW}" bash "${CATALOG}/bootstrap/data-root/data-root-layout.sh"
sudo DATA_ROOT="${NEW}" bash "${CATALOG}/bootstrap/data-root/data-root-perms.sh"
sudo DATA_ROOT="${NEW}" bash "${CATALOG}/bootstrap/opencloud/opencloud-check.sh"
```

If you keep a checkout under `/home/pilot/...`, point `CATALOG` at that repo root instead.

## 8. Prove it before unplugging the USB

```text
podman ps --format 'table {{.Names}}\t{{.Status}}'
sudo getfattr -d "${NEW}/users/faiz" | grep space
```

Browser: `https://cloud.home.lan` as **faiz** — Personal still lists. Vaultwarden / Authelia still log in.

HTPC (if NFS stacks are up): Explorer/SMB and a WSL NFS `ls` of `/shared` still work (`bootstrap/omv/README.md` smoke test).

## 9. Unplug the USB only after that

```text
sudo podman stop opencloud vaultwarden authelia pihole wireguard \
  jotty linkding rustdesk bytestash glances homepage
sudo umount "${OLD}"
```

Workbench: unmount/wipe the USB filesystem if OMV still lists it. Physically remove the USB.

Start stacks again (or Materia apply). Confirm OpenCloud once more.

Keep the USB intact (unmounted) for a day if you want a rollback copy. After that it is spare.

## If something fails

| Symptom | What to do |
|---|---|
| `setMountPoint` / disk missing in OMV | Disk was mounted via a plain fstab line first. Unmount, remove that line, then setMountPoint / Workbench Mount. |
| `getfattr` empty on `${NEW}/users/faiz` | Recopy with `-aAXH`. Do not change `DATA_ROOT` yet. |
| OpenCloud blank after switch | Inspect mounts: still on `OLD` uuid means attribute `DATA_ROOT` or Redeploy did not apply. |
| `shared/files` / `photos` NOT bound after copy | Expected: rsync duplicated trees. Merge into `projects/…`, empty household path, `publish` (see §7). |
| NFS `permission denied` / HTPC `:/shared` hangs | Hollow `/export/shared` or duplicate NFS clients. Re-run `omv-nfs.sh` with new `DATA_ROOT`; `ls /export/shared/media` must work on Core. |
| Pi-hole / Authelia unhappy | Those bind `${DATA_ROOT}/system/...`. Redeploy those stacks after the variable change. |
