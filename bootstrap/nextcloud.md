# Nextcloud first-run (PostgreSQL)

The Nextcloud stack on the HTPC includes a Postgres sidecar (`nextcloud-db`). The database is **not** on the Windows LAN. Do not type `HTPC_UPSTREAM` or port `5432` into the installer. Do not open 5432 in the Windows firewall.

Files stay on NFS (`shared/files`, `shared/photos`, `users`). `/config` and Postgres data are local Docker volumes.

## 1. Secret (existing Core)

If this site already ran `core.sh` before `NEXTCLOUD_DB_PASSWORD` existed, add it in Komodo. Do not re-run bootstrap only for this key.

1. Generate a password on any machine: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → add **`NEXTCLOUD_DB_PASSWORD`** with that value. Mark it a secret.
3. Write the value down. The installer asks for it; Komodo will not show it again.

New Core installs get the key from `core.sh` into `/etc/komodo/core.config.toml`.

## 2. Deploy this catalog

Commit and push to the catalog origin (Gitea). Wait for ResourceSync (or execute the sync). Komodo → **Stacks** → **nextcloud** → **Deploy**.

On the HTPC:

```text
docker ps --filter name=nextcloud --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You want `nextcloud` **Up** and `nextcloud-db` **Up (healthy)**. `nextcloud` should show `8080->443`. `nextcloud-db` must **not** list `5432` on the host.

## 3. Wipe a failed installer

If you already opened the wizard (SQLite or a LAN Postgres IP), the local config volume is dirty. On the HTPC:

```text
docker stop nextcloud
docker rm nextcloud
docker volume rm nextcloud-config
```

Do **not** delete `nextcloud-files`, `nextcloud-photos`, or `nextcloud-users`.

Delete `nextcloud-postgres` only if Postgres was created with the **wrong** password (then also recreate `nextcloud-db` via Deploy):

```text
docker stop nextcloud-db
docker rm nextcloud-db
docker volume rm nextcloud-postgres
```

Deploy **nextcloud** again in Komodo. Wait until `nextcloud-db` is healthy.

## 4. Installer

Open **`https://nextcloud.<DOMAIN>`** (the same `DOMAIN` as `https://ops.<DOMAIN>`). Use `nextcloud.`, not `cloud.`.

| Field | Value |
|---|---|
| Username | `NEXTCLOUD_ADMIN_USER` (bootstrap / Komodo) |
| Password | `NEXTCLOUD_ADMIN_PASSWORD` |
| Storage & database | Expand this section |
| Data folder | Leave `/data` |
| Database | **PostgreSQL** |
| Database user | `nextcloud` |
| Database password | `NEXTCLOUD_DB_PASSWORD` (not the admin password) |
| Database name | `nextcloud` |
| Database host | `postgres` |

Host is the word `postgres` — Compose DNS, not an IP, not `localhost`, not `host.docker.internal`.

Click **Install**. Wait; first run can take a minute.

## 5. External storage

1. **Apps** → enable **External storage support**.
2. **Administration settings** → **External storage**.
3. Add three **Local** mounts (checkmark to save each row):

| Folder name | Path |
|---|---|
| Household files | `/data/shared/files` |
| Household photos | `/data/shared/photos` |
| Users | `/data/users` |

## If it fails

| Symptom | What to do |
|---|---|
| `connection to server at "192.168.…" refused` | Host is still a LAN IP. Use `postgres`. |
| `password authentication failed` | Secret does not match the volume. Set `NEXTCLOUD_DB_PASSWORD` in Komodo, wipe `nextcloud-postgres` and `nextcloud-config`, Deploy, retry. |
| `nextcloud-db` never healthy | Stack env missing `NEXTCLOUD_DB_PASSWORD`. Add the secret, Deploy. |
| Untrusted domain | Open `https://nextcloud.<DOMAIN>` only. |
