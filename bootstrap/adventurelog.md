# Adventure Log first-run

Adventure Log runs on **periphery**. PostGIS and media are local HTPC volumes. Caddy is `https://travel.<DOMAIN>` (`trips.` and `adventurelog.` 301 there).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Adventure Log existed, add the keys in Komodo. Do not re-run bootstrap only for these.

1. Generate two passwords: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`ADVENTURELOG_POSTGRES_PASSWORD`** and **`ADVENTURELOG_ADMIN_PASSWORD`**. Mark both secrets.
3. Write down the admin password. User is `admin`. Email is `admin@<DOMAIN>`.

New Core installs get both keys from `core.sh` into `/etc/komodo/core.config.toml`. `OIDC_CLIENT_SECRET` is the shared Authelia client secret (same script).

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **adventurelog** → **Deploy** (Redeploy if the hook files changed). Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **8015** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=adventurelog --format "table {{.Names}}\t{{.Status}}"
```

You want `adventurelog` and `adventurelog-db` **Up**. First boot can take a couple of minutes (healthcheck start period). Logs should include `adventurelog-oidc: SocialApp authelia ready`.

## 3. Login

Open **`https://travel.<DOMAIN>`** (not `trips.` or `adventurelog.`). Local **Sign Up** stays closed (`DISABLE_REGISTRATION`). Use **Login** → **Authelia**. First Authelia login as **faiz** or **diana** creates a normal user; elevate **faiz** in Adventure Log.

Local `admin` / `ADVENTURELOG_ADMIN_PASSWORD` is break-glass only (Django admin). Changing the Komodo admin secret later does not update an existing Django user.

Maps need outbound HTTPS from the HTPC. That is expected.

## If it fails

| Symptom | What to do |
|---|---|
| `travel.<DOMAIN>` does not load while the stack is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:8015/ \| head` |
| CSRF / login ignored | Use `https://travel.<DOMAIN>` only. `SITE_URL` and Homepage must match that origin. Redeploy **adventurelog** after the catalog pull |
| Login has no Authelia button | Redeploy **adventurelog** (needs `OIDC_CLIENT_SECRET` and `seed-oidc.py`). Logs should show `SocialApp authelia ready` |
| Authelia succeeds, then Sign Up Closed | You used Sign Up. Use **Login** → **Authelia**. Redeploy if `SOCIALACCOUNT_ALLOW_SIGNUP` is missing |
| Authelia button → Server Error (500) / `CERTIFICATE_VERIFY_FAILED` | Caddy `tls internal`. Redeploy **adventurelog** so the sitecustomize TLS skip is mounted |
| Authelia succeeds, then Third-Party Login Failure | Redeploy **authelia** (Adventure Log claims policy + `client_secret_post`) and **adventurelog**. Clear cookies for `travel.<DOMAIN>` and `.<DOMAIN>`, then retry |
| Password rejected after a Komodo secret change | First-boot password is frozen in Postgres. On the HTPC: `docker exec -it adventurelog python manage.py changepassword admin` |
| Database connection failed | `ADVENTURELOG_POSTGRES_PASSWORD` must match on app and db. Changing it later does not update an existing PostGIS volume |
