# ByteStash first-run

ByteStash runs on **Core** (edge network). Snippets live under `${DATA_ROOT}/system/bytestash`. Caddy is `https://snip.<DOMAIN>` (`snippets.` and `bytestash.` 301 there).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before ByteStash existed, add the keys in `/etc/materia/site.env`. Do not re-run bootstrap only for these.

1. Generate a JWT secret: `openssl rand -hex 24`
2. Set **`BYTESTASH_JWT_SECRET`** in `/etc/materia/site.env` (and sops attributes).
3. Variables: **`BYTESTASH_ALLOW_NEW_ACCOUNTS`** = `true` (not a secret) until the household account exists.

New Core installs get both keys from `core.sh` into `/etc/materia/core.config.toml`.

Also run `data-root-perms.sh` so `system/bytestash` exists.

## 2. Deploy

Commit and push to the catalog git origin. Wait for Materia, then re-apply **caddy** and **homepage**.

On Core:

```text
podman ps --filter name=bytestash --format "table {{.Names}}\t{{.Status}}"
```

You want `bytestash` **Up**. It must **not** publish 5000 on the LAN.

## 3. First account

Open **`https://snip.<DOMAIN>`**. Create or keep the local household account as break-glass, then set **`BYTESTASH_ALLOW_NEW_ACCOUNTS`** to `false` in attributes and re-apply (Materia / systemd) **bytestash**. Authelia OIDC is on; first Authelia login as **faiz** or **diana** creates a ByteStash user. Elevate **faiz** in ByteStash. Changing `BYTESTASH_JWT_SECRET` later signs everyone out.

## If it fails

| Symptom | What to do |
|---|---|
| `snip.<DOMAIN>` does not load while `bytestash` is Up | re-apply (Materia / systemd) **caddy**. Then `podman exec caddy wget -S -O- --timeout=10 http://bytestash:5000/ \| head` |
| Host / CSRF errors | `ALLOWED_HOSTS` must be `snip.<DOMAIN>`. re-apply (Materia / systemd) **bytestash** after the catalog pull |
| Authelia `invalid_request` | ByteStash builds `redirect_uri` from Host. Authelia only allows `https://snip.<DOMAIN>/api/auth/oidc/callback`. re-apply (Materia / systemd) **caddy** and **authelia** |
| Cannot create the first user | `BYTESTASH_ALLOW_NEW_ACCOUNTS` must be `true` for that first visit |
