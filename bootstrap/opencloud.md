# OpenCloud first-run

OpenCloud runs on **Core** (edge network). Files are PosixFS on local disk: personal space `users/<username>/`, household Spaces `shared/files` and `shared/photos`. Do not point it at HTPC NFS.

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

## 3. Login and users

Open **`https://cloud.<DOMAIN>`**. Log in as `admin` / `OPENCLOUD_ADMIN_PASSWORD`.

Create household users whose **usernames match** `users/<name>` directories (`faiz`, `diana`, …). Each personal space is that directory (`files/` and `photos/` at the space root).

Optional: create project Spaces named **`files`** and **`photos`** if they do not appear from disk. Those map to `shared/files` and `shared/photos`.

## 4. Phone auto-upload (camera backup)

Install the OpenCloud iOS/Android app. Server URL: `https://cloud.<DOMAIN>` (WireGuard when off-LAN).

In app settings, enable automatic **picture** and **video** uploads. Set the destination to Personal → **`photos`**, not the default `CameraUpload` folder.

Leave Immich mobile backup **off**. Immich only indexes `users/<user>/photos`.

Android cannot yet auto-upload arbitrary folders (WhatsApp, Documents). Use the share sheet or the desktop client for those.

## 5. Remove leftover Nextcloud

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
| `extended attributes not supported` | Data disk must allow `user_xattr`. Do not move OpenCloud to HTPC NFS. |
| Permission denied on `users/<name>` | Re-run `bootstrap/data-root-perms.sh` as root. |
| Collabora iframe blocked / blank | Confirm `collabora` is Up on the HTPC and `office.<DOMAIN>` resolves to Core Caddy. |
| Secret does not match | Set `OPENCLOUD_ADMIN_PASSWORD` in Komodo, Redeploy. `opencloud init` only applies the password on first config create; wipe `${DATA_ROOT}/system/opencloud/config` only if you accept a fresh IDM. |
