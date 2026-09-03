# OpenCloud first-run

OpenCloud runs on **Core** (edge network). Personal space is PosixFS on `users/<username>/`. Household `shared/files` and `shared/photos` stay SMB (and Immich NFS). Do not point OpenCloud at HTPC NFS, and do not bind those shared trees as OpenCloud Spaces.

Caddy is `https://cloud.<DOMAIN>`. `nextcloud.` and `nc.` redirect here.

Collabora is a separate periphery stack (`https://office.<DOMAIN>`). OpenCloud is already configured to use it.

## 1. Secrets (existing Core)

If this site already ran `core.sh` before `OPENCLOUD_ADMIN_PASSWORD` existed, add it in Komodo. Do not re-run bootstrap only for this key.

1. Generate a password: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → add **`OPENCLOUD_ADMIN_PASSWORD`**. Mark it a secret.
3. Write it down. That is the built-in user `admin`.

New Core installs get the key from `core.sh` into `/etc/komodo/core.config.toml`.

Also run `data-root-perms.sh` so `${PUID}` can write `users/<user>/` (OpenCloud runs as PUID:PGID).

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **opencloud** → **Deploy**.

On Core:

```text
docker ps --filter name=opencloud --format "table {{.Names}}\t{{.Status}}"
```

You want `opencloud` **Up**. It must **not** publish 9200 on the LAN (Caddy uses the edge network).

If logs show `posixfs-xattr-check` or `mkdir …/storage/metadata: permission denied`, Docker already created `data/storage` as root. On Core (container stopped is fine):

```text
sudo docker stop opencloud
sudo mkdir -p /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/posix
sudo chown -R 1000:1000 /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud
```

Use this site’s `DATA_ROOT` and `PUID`/`PGID` if they are not those values. Then Redeploy **opencloud** after the catalog that mounts PosixFS at `/posix` is synced.

If logs then show `error parsing mapping JSON` / `Failed service 'search'`, the Bleve index was left empty by the earlier crash. Wipe **only** the search dir (not `config`, `posix`, or household files):

```text
sudo docker stop opencloud
sudo rm -rf /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/data/search
sudo docker start opencloud
```

If the UI then returns **Unexpected HTTP response: 500** on login, config and IDM are out of sync (typical after a crash-loop `init`). Wipe **both** `config` and `data` so `opencloud init` can run again. Do **not** delete `posix/`, `users/`, `shared/`, or `radicale/`. Confirm `OPENCLOUD_ADMIN_PASSWORD` is set in Komodo first (that becomes the `admin` password on this new init).

Do not use a shell glob (`config/*`). Those directories are `700` for UID 1000, so `sudo rm -rf …/*` expands as your user, matches nothing, and leaves `opencloud.yaml` / `idm.boltdb` in place.

```text
sudo docker stop opencloud
sudo find /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/config -mindepth 1 -delete
sudo find /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/data -mindepth 1 -delete
sudo chown -R 1000:1000 /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud
sudo ls -la /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/config
sudo ls -la /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/opencloud/data
sudo docker start opencloud
sudo docker logs -f opencloud
```

`ls` must show empty directories (only `.` and `..`). Logs must show `opencloud init` creating a new config, **not** `config file already exists`. Wait until the container stays **Up**, then log in as `admin` / `OPENCLOUD_ADMIN_PASSWORD`. Do not wipe `config` without `data` (or the reverse); that is what causes the 500.

## 3. Login and users

Open **`https://cloud.<DOMAIN>`**. Log in as `admin` / `OPENCLOUD_ADMIN_PASSWORD`.

Create household users whose **usernames match** `users/<name>` directories (`faiz`, `diana`, …). Set the role to **User**, not **User Light**.

A **User cannot create Spaces**. Personal appears on first login.

PosixFS root must be `system/opencloud/posix` (so `indexes/` and `uploads/` are not next to homes). Personal path is `users/<username>` via a bind of `${DATA_ROOT}/users` → `/posix/users`. If `users/` was used as POSIX_ROOT, CreateStorageSpace fails with `node.Xattrs /posix/uploads: no data available`.

Pre-existing `users/<name>` homes also block create (already-exists, no xattrs). Park them, let OpenCloud mkdir the space, then restore:

```text
DATA=/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47
sudo docker stop opencloud
sudo mkdir -p "$DATA/system/opencloud/posix/users"
sudo chown -R 1000:1000 "$DATA/system/opencloud/posix"
# Move internals out of the household tree if a previous layout put them there.
if [[ -d $DATA/users/indexes && ! -d $DATA/system/opencloud/posix/indexes ]]; then
  sudo mv "$DATA/users/indexes" "$DATA/system/opencloud/posix/indexes"
fi
if [[ -d $DATA/users/uploads && ! -d $DATA/system/opencloud/posix/uploads ]]; then
  sudo mv "$DATA/users/uploads" "$DATA/system/opencloud/posix/uploads"
fi
sudo chown root:1000 "$DATA/users"
sudo chmod 775 "$DATA/users"
sudo docker start opencloud
```

After Redeploy, confirm `TPL=users/{{.User.Username}}` and a bind `$DATA/users` → `/posix/users`. Park pre-existing homes with `opencloud-adopt-homes.sh park` (that moves them to `system/opencloud/incoming/`, not a sibling under `users/`). Sign in as each user. `getfattr -d $DATA/users/<name>` must show `user.oc.space.id`. Then `opencloud-adopt-homes.sh restore`.

The Android app treats “no Personal space” as User Light even when the admin role is User. When Personal works in the browser, remove the account from the app and add it again.

Do **not** create project Spaces for `shared/files` or `shared/photos`. Those stay SMB; Immich indexes them over NFS.

## 4. Phone auto-upload (camera backup)

Install the OpenCloud iOS/Android app. Server URL: `https://cloud.<DOMAIN>` (WireGuard when off-LAN).

In app settings, enable automatic **picture** and **video** uploads. Set the destination to Personal → **`photos`**, not the default `CameraUpload` folder.

Leave Immich mobile backup **off**. Immich only indexes `users/<user>/photos`.

Android cannot yet auto-upload arbitrary folders (WhatsApp, Documents). Use the share sheet or the desktop client for those.

## 5. Calendar and contacts (Radicale)

OpenCloud proxies authenticated CalDAV/CardDAV to a Radicale sidecar on the edge network. There is no calendar UI in OpenCloud. Clients: Apple Calendar/Contacts, Thunderbird, DAVx⁵. Server URL is `https://cloud.<DOMAIN>` (well-known discovery). Most clients cannot use OIDC; create an **App Token** in the OpenCloud user settings and use that as the password.

Radicale collections live in `${DATA_ROOT}/system/opencloud/radicale`. Do not publish 5232. Wipe of OpenCloud `config`/`data` must not delete this directory.

Existing Core: `sudo mkdir -p ${DATA_ROOT}/system/opencloud/radicale` then `sudo chown -R ${PUID}:${PGID} ${DATA_ROOT}/system/opencloud` (or re-run `data-root-perms.sh`). Redeploy **opencloud**. If `radicale` was Restarting, Redeploy after this catalog pull (the image CMD listens on IPv6 and exits on this host).

## 6. Remove leftover Nextcloud

After ResourceSync no longer lists `nextcloud`, delete that stack in Komodo if it is still present. On the HTPC:

```text
docker stop nextcloud nextcloud-db
docker rm nextcloud nextcloud-db
docker volume rm nextcloud-config nextcloud-postgres
```

Do **not** delete NFS volumes or files under `shared/` and `users/`.

## If it fails

| Symptom | What to do |
|---|---|
| `cloud.<DOMAIN>` does not load while `opencloud` is Up | Caddyfile change is not applied by deploying OpenCloud. Komodo → **caddy** → **Redeploy**. Then from Core: `docker exec caddy wget -S -O- --timeout=10 http://opencloud:9200/ \| head`. You want HTTP 200, not `no such host` or connection refused. |
| `posixfs-xattr-check` or `mkdir …/storage/metadata: permission denied` | Nested Docker binds created `data/storage` as root. Stop the container, `chown -R ${PUID}:${PGID}` `system/opencloud`, ensure `posix/` exists, Redeploy with PosixFS at `/posix`. |
| `error parsing mapping JSON` / search service | Empty Bleve index from a failed first start. Stop the container, `rm -rf ${DATA_ROOT}/system/opencloud/data/search`, start again. |
| Login: Unexpected HTTP response: 500 | Built-in IDM bolt-store does not match `opencloud.yaml` (crash-loop init, or config wiped without data). Confirm the log has `idm`/`idp` LDAP 49 or `not found`. Wipe **both** `${DATA_ROOT}/system/opencloud/config` and `.../data` (not `posix`, `users`, `shared`, or `radicale`), start again so `init` reseeds. |
| `extended attributes not supported` | Data disk must allow `user_xattr`. Do not move OpenCloud to HTPC NFS. |
| Permission denied on `users/<name>` | Re-run `bootstrap/data-root-perms.sh` as root. |
| Admin Settings → Spaces is empty / faiz has no Personal | Household `users/<name>` already existed, so CreateStorageSpace never indexed a space. Run `opencloud-adopt-homes.sh park`, log in as each user, then `restore`. Confirm with `getfattr -d ${DATA_ROOT}/users/faiz` (`user.oc.space.id`). |
| Creating a Space fails / `node.Xattrs /posix/projects/photos: no data available` | Do not create project Spaces for `shared/files` or `shared/photos`. Personal space is `users/<name>`. Drop those nested binds (catalog), `rm -rf …/posix/projects`, Redeploy **opencloud**. |
| Collabora iframe blocked / blank | Confirm `collabora` is Up on the HTPC and `office.<DOMAIN>` resolves to Core Caddy. |
| CalDAV/CardDAV client cannot discover | URL is `https://cloud.<DOMAIN>` (not a LAN port). Use an App Token, not the login password. Redeploy **opencloud** after this catalog pull. From Core: `docker exec caddy wget -S -O- --timeout=5 http://opencloud:9200/.well-known/caldav \| head`. |
| `radicale` Restarting / Exited | Image default listens on `[::]:5232`. Redeploy **opencloud** after this catalog pull (IPv4-only `--hosts`). If logs say permission denied: `mkdir` and `chown ${PUID}:${PGID}` `${DATA_ROOT}/system/opencloud/radicale`, then Redeploy. `docker logs radicale` |
| Secret does not match | `IDM_ADMIN_PASSWORD` applies only on `opencloud init`. Changing the Komodo secret later does not update a live IDM. Reset with `opencloud idm resetpassword`, or wipe **both** config and data and init again. Do **not** delete `radicale/`. |
