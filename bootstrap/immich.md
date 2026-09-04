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

Open **`https://photos.<DOMAIN>`**. Create the Immich admin account (this is not `IMMICH_DB_PASSWORD`). That local admin is break-glass.

## OIDC (Authelia)

Immich has no compose OAuth (config file would freeze every admin setting). After the wizard, set Administration → Settings → OAuth once:

| Field | Value |
|---|---|
| Issuer URL | `https://auth.<DOMAIN>` |
| Client ID | `immich` |
| Client Secret | Komodo secret `OIDC_CLIENT_SECRET` |
| Scope | `openid profile email` |
| Token Endpoint Auth Method | `client_secret_basic` |
| Auto Register | on |
| Button text | `Login with Authelia` |

Enable **PKCE** if the form has a checkbox (Authelia requires it).

Discovery runs **inside the Immich container**, not in the browser. Docker Desktop does not use Pi-hole, so the catalog sets `extra_hosts` for `auth.<DOMAIN>` → `NAS_LAN_IP` and `NODE_TLS_REJECT_UNAUTHORIZED=0` (Caddy `tls internal`). Redeploy **immich** after that catalog lands, then save OAuth again.

The Immich image has no `wget`. From the HTPC this must print `200` and JSON (not `ENOTFOUND` / timeout):

```text
docker exec -e NODE_TLS_REJECT_UNAUTHORIZED=0 immich node -e "fetch('https://auth.<DOMAIN>/.well-known/openid-configuration').then(async r=>{console.log(r.status);console.log(await r.text())}).catch(e=>{console.error(e);process.exit(1)})"
```

If that times out even to `https://<NAS_LAN_IP>/`, a Compose network is overlapping the LAN (`192.168.0.0/16`). Fix Engine JSON first — see [periphery.md](periphery.md) §7.

The Windows browser is a different path. Homepage working only proves Pi-hole → Caddy for `dash.`. Try `https://auth.<DOMAIN>` and `https://cloud.<DOMAIN>` in Edge. If those fail too, `nslookup auth.<DOMAIN>` should return `NAS_LAN_IP`. First Authelia login as **faiz** or **diana** creates a normal Immich user. Elevate **faiz** in Immich.

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
