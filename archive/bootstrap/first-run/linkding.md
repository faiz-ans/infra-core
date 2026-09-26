# Linkding first-run

Linkding runs on **Core** (edge network). SQLite lives under `${DATA_ROOT}/system/linkding`. Caddy is `https://links.<DOMAIN>` (`bookmarks.` and `linkding.` are aliases).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Linkding existed, add the keys in `/etc/infra-core/site.env`. Do not re-run bootstrap only for these.

1. Variables: **`LINKDING_SUPERUSER_NAME`** = `admin` (not a secret).
2. Generate a password: `openssl rand -hex 24`
3. Set **`LINKDING_SUPERUSER_PASSWORD`** in `/etc/infra-core/site.env` (and sops attributes).
4. Write it down. That is the first login.

New Core installs get both keys from `core.sh` into `/etc/infra-core/site.env`.

Also run `data-root-perms.sh` so `system/linkding` exists.

## 2. Deploy

Re-apply with `apply.sh` **caddy** and **homepage**.

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
| `links.<DOMAIN>` does not load while `linkding` is Up | re-apply (apply.sh / systemd) **caddy**. Then `podman exec caddy wget -S -O- --timeout=10 http://linkding:9090/ \| head` |
| Authelia ok, then Linkding cannot finish OIDC | Core `site` cannot hairpin `NAS_LAN_IP:443`. Catalog `hostAliases` `auth.<DOMAIN>` → `SITE_HOST_LOOPBACK`. Same as OpenCloud; see `authelia.md`. |
| CSRF verification failed | Confirm `LD_CSRF_TRUSTED_ORIGINS` includes `https://links.<DOMAIN>` (re-apply (apply.sh / systemd) **linkding** after the catalog pull) |
| Secret does not match | `LD_SUPERUSER_*` applies only when that user does not already exist |
