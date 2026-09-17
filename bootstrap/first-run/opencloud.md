# OpenCloud first-run (greenfield)

OpenCloud on **Core** (edge): PosixFS **documents** and **camera rolls** only.

| OpenCloud space | On disk | Who uses it |
|---|---|---|
| Personal | `users/<user>/files` | People + SMB |
| `photos-<user>` | `users/<user>/photos` | That user + phone ingest → Immich |
| `shared` | `shared/files` | Household docs + SMB |

`shared/{media,games,photos,downloads,cameras}` stay on SMB/NFS for Jellyfin/Arr/qBit/Kodi/Immich/Frigate. They are **not** OpenCloud spaces.

**Empty disk:** OpenCloud creates space roots → publish binds → layout → NFS.  
**Remounted data disk (this site):** if `getfattr` shows `user.oc.space.*` on `users/<user>/files` and `system/opencloud/projects/shared`, **do not** create Space `shared` again. Phase A remounts the tree; then layout + NFS. Park/adopt only if `system/opencloud/{config,data}` is corrupt.  
**Park/restore** utilities: `opencloud-adopt-homes.sh`, `opencloud-adopt-shared.sh`, `opencloud-adopt-photos.sh`.

## Greenfield checklist (empty disk)

### 0. Topology and host prep

1. Confirm `[Hosts.core]` includes `opencloud` (`Roles.core-bootstrap`).
2. Bootstrap Core (`core.sh`): Podman, OMV, Authelia `users.yml` if missing, **`data-root-prep.sh`**. Materia is optional and not required here.
3. `/etc/infra-core/site.env` includes **`OPENCLOUD_ADMIN_PASSWORD`**.

### 1. Phase A apply

```text
sudo bash bootstrap/apply.sh --role core-bootstrap
```

Re-apply **caddy** if the Caddyfile just gained `cloud.` / `office.`.

```text
podman ps --filter name='opencloud|radicale|collabora|caddy|authelia' --format 'table {{.Names}}\t{{.Status}}'
```

### 2. Login (Personal = files/)

Open `https://cloud.<DOMAIN>` → Authelia as an **admins** user (creates `users/<user>/files`). Then each household user.

`users/admin` is break-glass OpenCloud admin — leave it. Create an **App Token** for CalDAV/clients.

### 3. Space `shared` + publish onto `shared/files`

As an OpenCloud admin: Spaces → New Space → name exactly **`shared`** → add household members.

```text
DATA=/srv/dev-disk-by-uuid-…
sudo getfattr -d $DATA/system/opencloud/projects/shared | grep space.id
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-shared.sh publish
sudo stat -c '%d:%i' $DATA/shared/files $DATA/system/opencloud/projects/shared
```

### 4. Photos spaces + layout + shares

Regular users cannot create Project Spaces. As admin, for each household user: Spaces → New Space → name exactly **`photos-<user>`**. Members → add **only that user** with **Can manage**. If you created someone else’s space (example `photos-diana`), **remove yourself** so it leaves your sidebar. Admins still see every space under Settings → Spaces (name/quota/members only — not the files).

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh publish
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh restore
sudo DATA_ROOT=$DATA bash bootstrap/data-root/data-root-layout.sh
```

Layout creates `shared/media`, household `shared/photos`, `users/<name>/photos` ACLs/sticky. Then OMV SMB/NFS (`bootstrap/omv/README.md`) for `shared` and `users`.

Host timer assimilates SMB writes OpenCloud’s inotify miss (`opencloud-posix-scan.timer`). `core.sh` enables it (Layer 0). `data-root-layout.sh` starts a catch-up oneshot. It scans **`users/<u>/files` and `/posix/projects` only** (not `/posix/users`). Re-run `bootstrap/opencloud/opencloud-posix-scan.sh` only if `systemctl is-enabled opencloud-posix-scan.timer` is not enabled.

### 5. Phase B stacks

Add the `core-full` / `mantle-full` roles in `MANIFEST.toml` when you want them. Apply Immich, Jellyfin, etc. with `apply.sh --role core-full` / `mantle-full`. Do not install idle mantle `*-full`.

### 6. Verify

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-check.sh
```

### Collabora / Radicale / phone

- Collabora: catalog `COLLABORATION_APP_PROOF_DISABLE` + `collabora-ca`; open a document once.
- CalDAV: `https://cloud.<DOMAIN>`, username = OpenCloud user, password = App Token.
- Phone auto-upload → space **`photos-<user>`** (the space root, not Personal and not a `CameraUpload` folder). Immich mobile backup off.

---

## Existing site (whole `shared/` was the space)

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-shared.sh narrow
```

That umounts the old bind, leaves media/games on `shared/`, and rebinds the space onto `shared/files`. Then re-apply (apply.sh / systemd) **opencloud** (new Personal template), then:

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-homes.sh park
# log in as each user
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-homes.sh restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh park
# create Spaces photos-faiz, photos-diana; only that user as Can manage (remove yourself from the other)
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh publish
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh restore
sudo DATA_ROOT=$DATA bash bootstrap/data-root/data-root-layout.sh
sudo bash /tmp/opencloud-posix-scan.sh   # after scp of the new scan script
sudo systemctl start opencloud-posix-scan.service
```

---

## If content already exists (park utilities)

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-homes.sh park
# login each user → restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-shared.sh park
# create Space shared → publish → restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud/opencloud-adopt-photos.sh park
# create photos-<user>; only that user as Can manage (remove yourself from the other)
sudo DATA_ROOT=$DATA bash bootstrap/data-root/data-root-layout.sh
```

---

## Appendix: if it fails

| Symptom | What to do |
|---|---|
| `cloud.<DOMAIN>` dead while `opencloud` Up | re-apply (apply.sh / systemd) **caddy** |
| Permission / xattr on first start | Rootless OpenCloud uses `UserNS=keep-id`. `apply.sh` / prep chown config/data/posix/radicale to PUID. Do not recreate spaces if `user.oc.space.*` exists. |
| Authelia ok, then “Not logged in / routine safety log out” | OpenCloud on `site` must fetch `https://auth.<DOMAIN>/.well-known/openid-configuration`. `NAS_LAN_IP:443` is connection refused (PREROUTING lan-bind does not hairpin). Catalog maps `auth.<DOMAIN>` → `169.254.1.2` and lan-bind OUTPUT `127.0.0.1:443` → Caddy `:8443`. Re-run `core-lan-bind.sh --enable`, then re-apply **opencloud**. Do not wipe posix/users/shared. |
| `files` has no space id after login | Personal already exists on `users/<user>` (template is only used at CreateStorageSpace). `opencloud-adopt-homes.sh relocate`, then restore. Do not drop-wrong-login again. |
| `shared/files` empty in UI but SMB has docs | Bind missing — `adopt-shared.sh publish` (inode check), not findmnt alone |
| Whole `shared/` still in OpenCloud | `adopt-shared.sh narrow` |
| OC→SMB works, SMB→OC does not | Install/reinstall `opencloud-posix-scan.sh` (scan users+projects only), `core-net.sh`, start the oneshot |
| `posixfs scan /posix` failed | Expected on the old script (`uploads/` + media). Use the new scanner |
| Collabora white iframe / ProofKeys | re-apply (apply.sh / systemd) collabora + opencloud; proof disable + CA |
| `radicale` permission denied | prep should have PUID-owned radicale data |
| Layout sticky missing | Re-run **data-root-layout.sh** after publish |
