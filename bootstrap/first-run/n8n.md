# n8n first-run

n8n runs on **mantle**. SQLite, credentials, and workflow data are a local WSL volume (`n8n-data`). Caddy is `https://flow.<DOMAIN>` (`n8n.` is an alias).

Scheduled workflows run only while surface is up. This catalog does not WAN-publish 5678; off-LAN use is WireGuard, same as every other LAN service.

## 1. Secrets (existing Core)

If this site already ran `core.sh` before n8n existed, add the key in `/etc/infra-core/site.env`. Do not re-run bootstrap only for this.

1. Generate a key: `openssl rand -hex 24`
2. Set **`N8N_ENCRYPTION_KEY`** in `/etc/infra-core/site.env` (and sops attributes).
3. Write it down. Without the same key, stored credentials cannot be decrypted.

New Core installs get the key from `core.sh` into `/etc/infra-core/site.env`.

## 2. Deploy

Re-apply with `apply.sh` **caddy** and **homepage**.

On mantle, allow Windows Firewall TCP **5678** from the LAN (Caddy). See `bootstrap/mantle/README.md`.

```text
podman ps --filter name=n8n --format "table {{.Names}}\t{{.Status}}"
```

You want `n8n` **Up**.

## 3. Owner account

Open **`https://flow.<DOMAIN>`**. The first visit creates the owner account. Changing `N8N_ENCRYPTION_KEY` later orphans every stored credential.

Webhook URLs must show `https://flow.<DOMAIN>/webhook/...`. If they show `localhost:5678`, re-apply (apply.sh / systemd) **n8n** after the catalog pull (`WEBHOOK_URL` / `N8N_HOST`).

Internet SaaS callbacks (GitHub, Stripe, …) cannot reach this host without WireGuard. LAN and VPN triggers are the intended use.

## If it fails

| Symptom | What to do |
|---|---|
| `flow.<DOMAIN>` does not load while the container is Up | re-apply (apply.sh / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=10 http://<SURFACE_UPSTREAM>:5678/ \| head` |
| Editor websocket drops | Caddy already proxies websockets. Confirm Windows Firewall **5678** |
| Credentials fail after re-apply (apply.sh / systemd) | `N8N_ENCRYPTION_KEY` must match the key used when credentials were saved |
| Webhook URL is localhost | `WEBHOOK_URL` must be `https://flow.<DOMAIN>/`. re-apply (apply.sh / systemd) **n8n** |
