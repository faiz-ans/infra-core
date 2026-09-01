# ZoneMinder first-run

ZoneMinder runs on **periphery**. MariaDB, config, and logs are local HTPC volumes. Event recordings are NFS `shared/cameras`. Caddy is `https://cams.<DOMAIN>` (`zm.` and `zoneminder.` are aliases).

## 1. Secrets and tree (existing site)

If this site already ran `core.sh` before ZoneMinder existed:

1. Generate a password: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`ZM_DB_PASSWORD`**. Mark it a secret.
3. On Core, run `data-root-perms.sh` so `shared/cameras` exists with the household ACLs. No new NFS export (`/shared` already includes `cameras/`).

New Core installs get `ZM_DB_PASSWORD` from `core.sh`.

## 2. Deploy (Docker Desktop)

ResourceSync leaves this stack `deploy = false`. Deploy it **alone**, after every other HTPC stack is healthy. Do not Execute a full periphery sync to start it.

The example ZoneMinder compose uses 1G `/dev/shm`. That OOMs Docker Desktop WSL2 when Jellyfin/Immich are already running: `zoneminder-db` comes up, `zoneminder` never does, other HTPC containers die, and Periphery goes NOT OK. The catalog uses 256MB shm and a 768MB memory cap. That reduces the chance of a VM OOM; it does not guarantee it. Do not Deploy until this catalog revision is on the origin Komodo polls, the ZoneMinder image is already pulled, and Periphery is OK.

On the HTPC, allow Windows Firewall TCP **8084** from the LAN (Caddy). See `bootstrap/periphery.md`.

**Before Deploy**, with Periphery already OK, pull the image (internet, not NFS):

```text
docker pull ghcr.io/zoneminder-containers/zoneminder-base:latest
docker pull mariadb:11
```

Then Komodo → **Stacks** → **zoneminder** → **Deploy**. Redeploy **caddy** and **homepage**.

If Periphery goes NOT OK during Deploy: the Docker VM is wedged (same as a full stack outage). Recreate Periphery the way that already worked for you (onboarding key) after Desktop is usable again. Do **not** Deploy ZoneMinder again until `docker images` lists `zoneminder-base` and Periphery is OK.

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
