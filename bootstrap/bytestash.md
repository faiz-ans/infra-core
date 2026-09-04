# ByteStash first-run

ByteStash runs on **Core** (edge network). Snippets live under `${DATA_ROOT}/system/bytestash`. Caddy is `https://snippets.<DOMAIN>` (`bytestash.` is an alias).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before ByteStash existed, add the keys in Komodo. Do not re-run bootstrap only for these.

1. Generate a JWT secret: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`BYTESTASH_JWT_SECRET`**. Mark it a secret.
3. Variables: **`BYTESTASH_ALLOW_NEW_ACCOUNTS`** = `true` (not a secret) until the household account exists.

New Core installs get both keys from `core.sh` into `/etc/komodo/core.config.toml`.

Also run `data-root-perms.sh` so `system/bytestash` exists.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **bytestash** → **Deploy**. Redeploy **caddy** and **homepage**.

On Core:

```text
docker ps --filter name=bytestash --format "table {{.Names}}\t{{.Status}}"
```

You want `bytestash` **Up**. It must **not** publish 5000 on the LAN.

## 3. First account

Open **`https://snippets.<DOMAIN>`**. Create or keep the local household account as break-glass, then set **`BYTESTASH_ALLOW_NEW_ACCOUNTS`** to `false` in Komodo and Redeploy **bytestash**. Authelia OIDC is on; first Authelia login as **faiz** or **diana** creates a ByteStash user. Elevate **faiz** in ByteStash. Changing `BYTESTASH_JWT_SECRET` later signs everyone out.

## If it fails

| Symptom | What to do |
|---|---|
| `snippets.<DOMAIN>` does not load while `bytestash` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://bytestash:5000/ \| head` |
| Host / CSRF errors | `ALLOWED_HOSTS` must include `snippets.<DOMAIN>`. Redeploy **bytestash** after the catalog pull |
| Cannot create the first user | `BYTESTASH_ALLOW_NEW_ACCOUNTS` must be `true` for that first visit |
