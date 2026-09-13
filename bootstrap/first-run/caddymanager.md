# CaddyManager first-run (experiment)

CaddyManager is a web UI for this site’s Caddy admin API. It is **`deploy = false`** until you opt in. GitOps still owns [`stacks/platform/caddy/Caddyfile`](../../stacks/platform/caddy/Caddyfile). A **Caddy Redeploy** reloads that file and **drops** any config that existed only in the UI.

Caddy is `https://traffic.<DOMAIN>` (`caddymanager.` 301 there). Authelia forward-auth is on the vhost (`admins` / **faiz** only), then CaddyManager’s own login.

The admin API listens on `0.0.0.0:2019` **inside** the Caddy container on `edge` only. Compose does **not** publish 2019 on the host.

## 1. Secrets (existing Core)

CaddyManager is skipped by `sync-komodo-secrets.sh` while `deploy = false`.

1. Set `deploy = true` in `stacks/komodo/fragments/caddymanager.inc`.
2. `python3 stacks/komodo/generate-stacks.py`
3. On Core: `sudo bash bootstrap/komodo/sync-komodo-secrets.sh` (generates `CADDYMANAGER_JWT_SECRET`).
4. Recreate Komodo Core so `[secrets]` reload.
5. Run `data-root-perms.sh` so `system/caddymanager` exists.

## 2. Deploy

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **caddymanager** → **Deploy**. Redeploy **authelia**, **caddy** (admin API + vhost) and **homepage**.

On Core:

```text
docker ps --filter name=caddymanager --format "table {{.Names}}\t{{.Status}}"
docker exec caddymanager-backend wget -S -O- --timeout=5 http://caddy:2019/config/ | head
```

You want `caddymanager-frontend` and `caddymanager-backend` **Up**. They must **not** publish 80 or 3000 on the LAN.

## 3. First login

Open **`https://traffic.<DOMAIN>`** (Authelia first). Default CaddyManager user is **`admin` / `caddyrocks`**. Change that password immediately.

Add this site’s Caddy as a server:

- Name: `core`
- Admin API: `http://caddy:2019`

Pull the running config. Treat the UI as a viewer / scratchpad. Put lasting routes in the catalog Caddyfile.

## If it fails

| Symptom | What to do |
|---|---|
| `traffic.<DOMAIN>` does not load | `deploy = true`, stack Up, Redeploy **caddy**. `docker exec caddy wget -S -O- --timeout=10 http://caddymanager-frontend:80/ \| head` |
| Forbidden / 403 | Authelia `default_policy` is deny. Redeploy **authelia** so `traffic.` is in the `admins` gate. Log in as **faiz** |
| Cannot reach admin API | Redeploy **caddy** after this catalog’s `admin 0.0.0.0:2019` block. From backend: `wget -S -O- --timeout=5 http://caddy:2019/config/` |
| Admin API origin rejected | Caddyfile `origins` must include `caddy:2019`. Redeploy **caddy** |
| CORS error | `CORS_ORIGIN` is `https://traffic.${DOMAIN}` (no trailing slash, primary host only) |
| UI config vanished after Redeploy | Expected. Catalog Caddyfile is source of truth |
| 2019 on the LAN | Compose must not list `2019:2019`. Remove it if you added it by hand |
| JWT errors after Redeploy | `CADDYMANAGER_JWT_SECRET` must stay fixed. Do not regenerate it |
