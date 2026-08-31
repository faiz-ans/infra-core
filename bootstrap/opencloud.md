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
| `extended attributes not supported` | Data disk must allow `user_xattr`. Do not move OpenCloud to HTPC NFS. |
| Permission denied on `users/<name>` | Re-run `bootstrap/data-root-perms.sh` as root. |
| Collabora iframe blocked / blank | Confirm `collabora` is Up on the HTPC and `office.<DOMAIN>` resolves to Core Caddy. |
| Secret does not match | Set `OPENCLOUD_ADMIN_PASSWORD` in Komodo, Redeploy. `opencloud init` only applies the password on first config create; wipe `${DATA_ROOT}/system/opencloud/config` only if you accept a fresh IDM. |
