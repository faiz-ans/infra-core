# n8n first-run

n8n runs on **periphery**. SQLite, credentials, and workflow data are a local HTPC volume (`n8n-data`). Caddy is `https://flow.<DOMAIN>` (`n8n.` is an alias).

Scheduled workflows run only while the HTPC is up. This catalog does not WAN-publish 5678; off-LAN use is WireGuard, same as every other LAN service.

## 1. Secrets (existing Core)

If this site already ran `core.sh` before n8n existed, add the key in Komodo. Do not re-run bootstrap only for this.

1. Generate a key: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`N8N_ENCRYPTION_KEY`**. Mark it a secret.
3. Write it down. Without the same key, stored credentials cannot be decrypted.

New Core installs get the key from `core.sh` into `/etc/komodo/core.config.toml`.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **n8n** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **5678** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=n8n --format "table {{.Names}}\t{{.Status}}"
```

You want `n8n` **Up**.

## 3. Owner account

Open **`https://flow.<DOMAIN>`**. The first visit creates the owner account. Changing `N8N_ENCRYPTION_KEY` later orphans every stored credential.

Webhook URLs must show `https://flow.<DOMAIN>/webhook/...`. If they show `localhost:5678`, Redeploy **n8n** after the catalog pull (`WEBHOOK_URL` / `N8N_HOST`).

Internet SaaS callbacks (GitHub, Stripe, …) cannot reach this host without WireGuard. LAN and VPN triggers are the intended use.

## If it fails

| Symptom | What to do |
|---|---|
| `flow.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:5678/ \| head` |
| Editor websocket drops | Caddy already proxies websockets. Confirm Windows Firewall **5678** |
| Credentials fail after Redeploy | `N8N_ENCRYPTION_KEY` must match the key used when credentials were saved |
| Webhook URL is localhost | `WEBHOOK_URL` must be `https://flow.<DOMAIN>/`. Redeploy **n8n** |
