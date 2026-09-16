# Linkding first-run

Linkding runs on **Core** (edge network). SQLite lives under `${DATA_ROOT}/system/linkding`. Caddy is `https://links.<DOMAIN>` (`bookmarks.` and `linkding.` are aliases).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Linkding existed, add the keys in `/etc/materia/site.env`. Do not re-run bootstrap only for these.

1. Variables: **`LINKDING_SUPERUSER_NAME`** = `admin` (not a secret).
2. Generate a password: `openssl rand -hex 24`
3. Set **`LINKDING_SUPERUSER_PASSWORD`** in `/etc/materia/site.env` (and sops attributes).
4. Write it down. That is the first login.

New Core installs get both keys from `core.sh` into `/etc/materia/core.config.toml`.

Also run `data-root-perms.sh` so `system/linkding` exists.

## 2. Deploy

Commit and push to the catalog git origin. Wait for Materia, then re-apply **caddy** and **homepage**.

On Core:

```text
podman ps --filter name=linkding --format "table {{.Names}}\t{{.Status}}"
```

You want `linkding` **Up**. It must **not** publish 9090 on the LAN.

## 3. Login

Open **`https://links.<DOMAIN>`**. Local `LINKDING_SUPERUSER_NAME` stays as break-glass. Authelia OIDC is on; first Authelia login as **faiz** or **diana** creates a Linkding user. Elevate **faiz** in Linkding. Changing the attribute later does not update an existing Django user.

## If it fails

| Symptom | What to do |
|---|---|
| `links.<DOMAIN>` does not load while `linkding` is Up | re-apply (Materia / systemd) **caddy**. Then `podman exec caddy wget -S -O- --timeout=10 http://linkding:9090/ \| head` |
| CSRF verification failed | Confirm `LD_CSRF_TRUSTED_ORIGINS` includes `https://links.<DOMAIN>` (re-apply (Materia / systemd) **linkding** after the catalog pull) |
| Secret does not match | `LD_SUPERUSER_*` applies only when that user does not already exist |
