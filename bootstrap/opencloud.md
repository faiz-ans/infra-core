# OpenCloud first-run

OpenCloud runs on **Core** (edge network). Personal space is PosixFS on `users/<username>/`. Household `shared/` is one Project Space (name exactly `shared`) on the same disk, synced with SMB like personal homes. Immich still indexes `shared/photos` over NFS. Do not point OpenCloud at HTPC NFS, and do not bind `shared/files` or `shared/photos` as nested mounts.

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

Open **`https://cloud.<DOMAIN>`**. Web login is Authelia OIDC (`faiz` and `diana`). The browser always goes to Authelia; there is no local `admin` password form while OIDC is on. Built-in **`admin`** / `OPENCLOUD_ADMIN_PASSWORD` remains break-glass for DAV / App Tokens (`PROXY_ENABLE_BASIC_AUTH`), not for elevating users in the UI.

Roles come from Authelia **groups** (OIDC claim `groups`):

| Authelia group | OpenCloud role |
|---|---|
| `admins` | `admin` (faiz) |
| `users` | `user` (diana; faiz also has this, but `admins` wins) |

After Redeploy with that mapping: log out of OpenCloud, sign in again as **faiz**, then create Project Spaces. Most CalDAV/CardDAV clients still cannot use OIDC — create an **App Token**.

Authelia autoprovisions `faiz` and `diana` with usernames that must match `users/<name>`. Do not create those users by hand unless Authelia is down.

A **User cannot create Spaces**. **Admin** (and Space Admin) can. Personal appears on first login.

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

## 3b. Household shared/ Project Space

CreateStorageSpace **refuses a path that already exists**. Binding `${DATA_ROOT}/shared` as the space root therefore always fails (even when empty after park). Catalog uses the same pattern as personal homes:

- Parent bind: `${DATA_ROOT}/system/opencloud/projects` → `/posix/projects`
- Space name **`shared`** creates `projects/shared` with xattrs
- `opencloud-adopt-shared.sh publish` bind-mounts that onto `${DATA_ROOT}/shared` (SMB/NFS) and adds an `/etc/fstab` line

Do not create separate Spaces for `files` or `photos`.

If you already parked (content in `incoming/shared`, empty `shared/`):

1. Push this catalog; Komodo → **opencloud** → **Redeploy**.
2. As **faiz**: Spaces → New Space → name **`shared`** → add **diana**.
3. Confirm: `getfattr -d $DATA/system/opencloud/projects/shared` shows `user.oc.space.id`.
4. Publish + restore:

```text
sudo DATA_ROOT=/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47 \
  bash bootstrap/opencloud-adopt-shared.sh publish
sudo DATA_ROOT=/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47 \
  bash bootstrap/opencloud-adopt-shared.sh restore
sudo bash bootstrap/data-root-perms.sh
```

Fresh site (not yet parked): `park` → Redeploy → create Space → `publish` → `restore`.

`STORAGE_USERS_POSIX_WATCH_FS=true` keeps SMB and OpenCloud in sync. First scan of a large `shared/` (media/games) can take a long time. Do **not** put Samba `force user` on the household `shared` share.

## 4. Phone auto-upload (camera backup)

Install the OpenCloud iOS/Android app. Server URL: `https://cloud.<DOMAIN>` (WireGuard when off-LAN).

In app settings, enable automatic **picture** and **video** uploads. Set the destination to Personal → **`photos`**, not the default `CameraUpload` folder.

Leave Immich mobile backup **off**. Immich only indexes `users/<user>/photos`.

Android cannot yet auto-upload arbitrary folders (WhatsApp, Documents). Use the share sheet or the desktop client for those.

## 5. Calendar and contacts (Radicale)

This stack follows the official overlay, not a custom Radicale setup:

- Docs: https://docs.opencloud.eu/docs/admin/configuration/radicale-integration/
- Compose overlay: https://github.com/opencloud-eu/opencloud-compose/blob/main/radicale/radicale.yml
- Config file: https://github.com/opencloud-eu/opencloud-compose/blob/main/config/radicale/config
- Proxy routes: https://github.com/opencloud-eu/opencloud-compose/blob/main/config/opencloud/proxy.yaml

OpenCloud authenticates CalDAV/CardDAV and forwards `/caldav`, `/carddav`, and `.well-known` to the `radicale` container. There is no calendar UI. Clients: Apple Calendar/Contacts, Thunderbird, DAVx⁵. URL is `https://cloud.<DOMAIN>` (well-known discovery). Most clients cannot use OIDC; create an **App Token** in OpenCloud user settings and use that as the password.

Catalog adaptations of that overlay (this repo has no Traefik / `opencloud-net`):

- Network is `edge` (same Docker DNS name `radicale` used in official `proxy.yaml`).
- Data bind is `${DATA_ROOT}/system/opencloud/radicale` → `/var/lib/radicale` (official `${RADICALE_DATA_DIR}`).
- `user:` is `${PUID}:${PGID}` (official `OC_CONTAINER_UID_GID`).

Do not publish 5232. Caddy already proxies all of `cloud.` to OpenCloud `:9200`. Wipe of OpenCloud `config`/`data` must not delete the Radicale data directory.

Official `.env.example` requires a bind-mounted Radicale data dir owned by the container uid/gid (default 1000:1000). Docker creates a missing bind source as **root**; Radicale then cannot write `collections/collection-root` and crash-loops. On Core that uid is `${PUID}:${PGID}` (this site: 1000). Existing Core — run this, then the container recovers on its next restart:

```text
docker inspect radicale --format '{{range .Mounts}}{{if eq .Destination "/var/lib/radicale"}}{{.Source}}{{end}}{{end}}'
sudo chown -R 1000:1000 "$(docker inspect radicale --format '{{range .Mounts}}{{if eq .Destination "/var/lib/radicale"}}{{.Source}}{{end}}{{end}}')"
sudo ls -la "$(docker inspect radicale --format '{{range .Mounts}}{{if eq .Destination "/var/lib/radicale"}}{{.Source}}{{end}}{{end}}')"
```

You want owner `1000` on `.` and `collections/`. No compose change and no Redeploy are required for this.

The official config bind is a **file**: `./config/radicale/config` → `/etc/radicale/config`. If that host path is a directory, Docker created it because the file was missing and Radicale exits. In the Komodo opencloud stack clone:

```text
# leftover from earlier catalog paths
sudo rm -rf radicale/config radicale.conf
# if Docker created the official path as a directory:
sudo rm -rf config/radicale/config
```

Then Redeploy **opencloud** so ResourceSync copies `config/radicale/config` as a file. Confirm with `docker logs radicale` if it still restarts.

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
| Creating a Space fails / `node.Xattrs /posix/projects/photos: no data available` | Do not bind `shared/files` or `shared/photos` as nested mounts. Use one Space named **`shared`** on the whole `${DATA_ROOT}/shared` bind. Drop leftover nested binds, `rm -rf …/posix/projects` children that are not the bind, Redeploy **opencloud**. |
| `shared` Space create fails / no space id | Do not bind `${DATA_ROOT}/shared` as the space root. Use parent bind `system/opencloud/projects`, create Space **`shared`**, then `opencloud-adopt-shared.sh publish` + `restore`. |
| Collabora iframe white / `unable to get local issuer certificate` | Collabora WOPI-fetches `https://cloud.<DOMAIN>` and must trust Caddy `tls internal`. Redeploy **collabora**. `docker logs collabora-ca` should show `wrote /ca/ca-bundle.crt`. CODE 26 is distroless — do not wrap it with a bash entrypoint. |
| Collabora `Unauthorized WOPI host` / CheckFileInfo 500 / OpenCloud `ProofKeys verification failed` | CODE sent no `X-WOPI-Proof` (distroless, no proof key). Catalog disables proof checks and writes `/etc/coolwsd/proof_key` via `collabora-ca`. Redeploy **opencloud** then **collabora**. |
| Collabora Unhealthy | CODE's `coolwsd --probe` dials HTTPS on 9980 while this stack uses HTTP behind Caddy. Catalog disables that healthcheck. `collabora-ca` must stay Up (not Exited). Redeploy **collabora**. |
| CalDAV/CardDAV client cannot discover | URL is `https://cloud.<DOMAIN>` (not a LAN port). Use an App Token, not the login password. Redeploy **opencloud** after this catalog pull. From Core: `docker exec caddy wget -S -O- --timeout=5 http://opencloud:9200/.well-known/caldav \| head`. |
| `radicale` Restarting / Exited | `docker logs radicale`. Config loaded but `Permission denied: '/var/lib/radicale/collections/collection-root'` with `owner=root(0)`: Docker created the bind as root — `chown -R 1000:1000` the host path from `docker inspect` (see §5). `IsADirectoryError`: official bind `config/radicale/config` must be a file — remove leftover directories in the stack clone, Redeploy **opencloud**. |
| Secret does not match | `IDM_ADMIN_PASSWORD` applies only on `opencloud init`. Changing the Komodo secret later does not update a live IDM. Reset with `opencloud idm resetpassword`, or wipe **both** config and data and init again. Do **not** delete `radicale/`. |
