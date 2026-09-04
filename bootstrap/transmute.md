# Transmute first-run

Transmute runs on **periphery**. Uploads, SQLite, and conversion output are a local HTPC volume (`transmute-data`). Caddy is `https://convert.<DOMAIN>` (`transmute.` is an alias).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Transmute existed, add the key in Komodo. Do not re-run bootstrap only for this.

1. Generate a secret: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`TRANSMUTE_AUTH_SECRET_KEY`**. Mark it a secret.

New Core installs get the key from `core.sh` into `/etc/komodo/core.config.toml`.

Without a fixed `AUTH_SECRET_KEY`, every container restart invalidates JWTs.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **transmute** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **3313** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=transmute --format "table {{.Names}}\t{{.Status}}"
```

You want `transmute` **Up** (healthy after the first minute). Video conversions use the HTPC CPU; that is expected.

## 3. Admin

Open **`https://convert.<DOMAIN>`** (Caddy sends `transmute.` there). Local admin stays as break-glass. Authelia OIDC is on (`Login with Authelia`). First Authelia login as **faiz** or **diana** creates a Transmute user (`OIDC_AUTO_CREATE_USERS`). Elevate **faiz** in Transmute.

## If it fails

| Symptom | What to do |
|---|---|
| `convert.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:3313/ \| head` |
| Logged out after Redeploy | `TRANSMUTE_AUTH_SECRET_KEY` must be set and unchanged |
| Authelia button → Internal Server Error | Token exchange hits `https://auth.<DOMAIN>` (Caddy `tls internal`). Redeploy **caddy** and **transmute**. `docker logs transmute` should show `transmute-oidc: PYTHONPATH sitecustomize ready` at start. |
