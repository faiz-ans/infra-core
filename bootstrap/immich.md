# Immich first-run (External Libraries)

Immich on the HTPC is the **gallery**. Photo originals stay on NFS (`shared/photos`, `users/<user>/photos`). Postgres, Redis, ML, and Immich’s own upload volume are local Docker volumes.

Phone camera ingest is **OpenCloud**, not Immich. See [`bootstrap/opencloud.md`](opencloud.md).

## 1. Secret (existing Core)

If this site already ran `core.sh` before `IMMICH_DB_PASSWORD` existed, add it in Komodo. Do not re-run bootstrap only for this key.

1. Generate a password: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → add **`IMMICH_DB_PASSWORD`**. Mark it a secret.

New Core installs get the key from `core.sh`.

## 2. Deploy

Komodo → **Stacks** → **immich** → **Deploy** (this site uses `compose.nfs.yaml`).

On the HTPC:

```text
docker ps --filter name=immich --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You want `immich` **Up** with `2283->2283`, `immich-db` **Up (healthy)**, plus `immich-ml` and `immich-redis`. `immich-db` must **not** list `5432` on the host.

## 3. Wizard

Open **`https://photos.<DOMAIN>`**. Create the Immich admin account (this is not `IMMICH_DB_PASSWORD`).

## 4. External Libraries

**Administration** → **External Libraries** (or **Libraries**):

| Library | Import path inside the container |
|---|---|
| Household photos | `/mnt/photos` |
| Each user | `/mnt/users/<user>/photos` |

Scan after adding. New OpenCloud phone uploads show up on the next scan (NFS has no reliable inotify from the HTPC).

Do **not** enable Immich mobile backup. That writes a second copy into the local `immich-upload` volume and leaves the `DATA_ROOT` photo trees unused.

## Wipe a failed DB only

If Postgres was created with the wrong password, wipe the local DB volume (not the NFS photo trees):

```text
docker stop immich immich-ml immich-db immich-redis
docker rm immich immich-ml immich-db immich-redis
docker volume rm immich-postgres
```

Do **not** delete `immich-photos` / `immich-users` (NFS) or files under `shared/photos` and `users/`. Redeploy **immich**.

## If it fails

| Symptom | What to do |
|---|---|
| `password authentication failed` | Secret does not match the volume. Set `IMMICH_DB_PASSWORD` in Komodo, wipe `immich-postgres`, Deploy. |
| `immich-db` never healthy | Stack env missing `IMMICH_DB_PASSWORD`. Add the secret, Deploy. |
| Empty timeline | External Library paths wrong or scan not run. Confirm `/mnt/photos` and `/mnt/users/<user>/photos` inside the `immich` container. |
