# Adventure Log first-run

Adventure Log runs on **mantle**. PostGIS and media are local WSL volumes. Caddy is `https://travel.<DOMAIN>` (`trips.` and `adventurelog.` 301 there).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Adventure Log existed, add the keys in `/etc/materia/site.env`. Do not re-run bootstrap only for these.

1. Generate two passwords: `openssl rand -hex 24`
2. Set **`ADVENTURELOG_POSTGRES_PASSWORD`** and **`ADVENTURELOG_ADMIN_PASSWORD`** in `/etc/materia/site.env` (and sops attributes).
3. Write down the admin password. User is `admin`. Email is `admin@<DOMAIN>`.

New Core installs get both keys from `core.sh` into `/etc/materia/site.env`. `OIDC_CLIENT_SECRET` is the shared Authelia client secret.

## 2. Deploy

Commit and push to the catalog git origin. Wait for Materia, then re-apply **caddy** and **homepage** (and **adventurelog** if the hook files changed).

On mantle, allow Windows Firewall TCP **8015** from the LAN (Caddy). See `bootstrap/mantle/README.md`.

```text
podman ps --filter name=adventurelog --format "table {{.Names}}\t{{.Status}}"
```

You want `adventurelog` and `adventurelog-db` **Up**. First boot can take a couple of minutes (healthcheck start period). Logs should include `adventurelog-oidc: SocialApp authelia ready`.

## 3. Login

Open **`https://travel.<DOMAIN>`** (not `trips.` or `adventurelog.`). Local **Sign Up** stays closed (`DISABLE_REGISTRATION`). Use **Login** → **Authelia**. First Authelia login as **faiz** or **diana** creates a normal user; elevate **faiz** in Adventure Log.

Local `admin` / `ADVENTURELOG_ADMIN_PASSWORD` is break-glass only (Django admin). Changing the attribute later does not update an existing Django user.

Maps need outbound HTTPS from surface. That is expected.

## If it fails

| Symptom | What to do |
|---|---|
| `travel.<DOMAIN>` does not load while the stack is Up | re-apply (Materia / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=10 http://<SURFACE_UPSTREAM>:8015/ \| head` |
| CSRF / login ignored | Use `https://travel.<DOMAIN>` only. `SITE_URL` and Homepage must match that origin. re-apply (Materia / systemd) **adventurelog** after the catalog pull |
| Login has no Authelia button | re-apply (Materia / systemd) **adventurelog** (needs `OIDC_CLIENT_SECRET` and `seed-oidc.py`). Logs should show `SocialApp authelia ready` |
| Authelia succeeds, then Sign Up Closed | You used Sign Up. Use **Login** → **Authelia**. re-apply (Materia / systemd) if `SOCIALACCOUNT_ALLOW_SIGNUP` is missing |
| Authelia button → Server Error (500) / `CERTIFICATE_VERIFY_FAILED` | Caddy `tls internal`. re-apply (Materia / systemd) **adventurelog** so the sitecustomize TLS skip is mounted |
| Authelia succeeds, then Third-Party Login Failure | re-apply (Materia / systemd) **authelia** (Adventure Log claims policy + `client_secret_post`) and **adventurelog**. Clear cookies for `travel.<DOMAIN>` and `.<DOMAIN>`, then retry |
| Password rejected after a attribute change | First-boot password is frozen in Postgres. On mantle: `podman exec -it adventurelog python manage.py changepassword admin` |
| Database connection failed | `ADVENTURELOG_POSTGRES_PASSWORD` must match on app and db. Changing it later does not update an existing PostGIS volume |
