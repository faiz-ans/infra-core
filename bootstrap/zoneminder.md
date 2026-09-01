# ZoneMinder first-run

ZoneMinder runs on **periphery**. MariaDB, config, and logs are local HTPC volumes. Event recordings are NFS `shared/cameras`. Caddy is `https://cams.<DOMAIN>` (`zm.` and `zoneminder.` are aliases).

## 1. Secrets and tree (existing site)

If this site already ran `core.sh` before ZoneMinder existed:

1. Generate a password: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`ZM_DB_PASSWORD`**. Mark it a secret.
3. On Core, run `data-root-perms.sh` so `shared/cameras` exists with the household ACLs. No new NFS export (`/shared` already includes `cameras/`).

New Core installs get `ZM_DB_PASSWORD` from `core.sh`.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **zoneminder** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **8084** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=zoneminder --format "table {{.Names}}\t{{.Status}}"
```

You want `zoneminder` and `zoneminder-db` **Up**.

## 3. UI and cameras

Open **`https://cams.<DOMAIN>`**. The image’s default web login is whatever ZoneMinder ships (often `admin` / `admin`); change it in Options immediately.

Add monitors for LAN cameras (RTSP). Events land in `shared/cameras` (SMB and restic). Do not point recordings at the HTPC SSD.

Live view through Caddy is HTTP. If a monitor is blank, check shm (`/dev/shm` tmpfs is 1G in the catalog) and that the camera is reachable from the HTPC, not only from Core.

## If it fails

| Symptom | What to do |
|---|---|
| `cams.<DOMAIN>` does not load while the stack is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:8084/ \| head` |
| NFS mount / permission denied on `/data` | Confirm `shared/cameras` exists and `data-root-perms.sh` was run. HTPC NFS client is the Core export of `/shared` |
| Database connection failed | `ZM_DB_PASSWORD` must match on both `zoneminder` and `zoneminder-db`. Changing it later does not update an existing MariaDB volume |
