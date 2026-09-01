# Linkding first-run

Linkding runs on **Core** (edge network). SQLite lives under `${DATA_ROOT}/system/linkding`. Caddy is `https://links.<DOMAIN>` (`bookmarks.` and `linkding.` are aliases).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Linkding existed, add the keys in Komodo. Do not re-run bootstrap only for these.

1. Variables: **`LINKDING_SUPERUSER_NAME`** = `admin` (not a secret).
2. Generate a password: `openssl rand -hex 24`
3. Komodo → **Settings** → **Secrets** → **`LINKDING_SUPERUSER_PASSWORD`**. Mark it a secret.
4. Write it down. That is the first login.

New Core installs get both keys from `core.sh` into `/etc/komodo/core.config.toml`.

Also run `data-root-perms.sh` so `system/linkding` exists.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **linkding** → **Deploy**. Redeploy **caddy** and **homepage**.

On Core:

```text
docker ps --filter name=linkding --format "table {{.Names}}\t{{.Status}}"
```

You want `linkding` **Up**. It must **not** publish 9090 on the LAN.

## 3. Login

Open **`https://links.<DOMAIN>`**. Log in as `LINKDING_SUPERUSER_NAME` / `LINKDING_SUPERUSER_PASSWORD`. Changing the Komodo secret later does not update an existing Django user; use Linkding’s own password change after the first login.

## If it fails

| Symptom | What to do |
|---|---|
| `links.<DOMAIN>` does not load while `linkding` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://linkding:9090/ \| head` |
| CSRF verification failed | Confirm `LD_CSRF_TRUSTED_ORIGINS` includes `https://links.<DOMAIN>` (Redeploy **linkding** after the catalog pull) |
| Secret does not match | `LD_SUPERUSER_*` applies only when that user does not already exist |
