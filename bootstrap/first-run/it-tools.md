# IT Tools first-run

IT Tools runs on **Core** (edge network). It is a stateless browser toolbox. Caddy is `https://it.<DOMAIN>` (`tools.` and `it-tools.` are aliases). The vhost is Authelia forward-auth (`users` — **faiz** and **diana**).

No Komodo secret. No data directory.

## 1. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **it-tools** → **Deploy**. Redeploy **caddy** and **homepage**.

On Core:

```text
docker ps --filter name=it-tools --format "table {{.Names}}\t{{.Status}}"
```

You want `it-tools` **Up**. It must **not** publish 80 on the LAN.

## 2. Use

Open **`https://it.<DOMAIN>`**. If you already logged in to Authelia on another app, this vhost will not show a login (SSO cookie). Confirm the gate with a private window, or log out at `https://auth.<DOMAIN>/logout` first. Redeploy **caddy** if a private window still skips Authelia.

## If it fails

| Symptom | What to do |
|---|---|
| `it.<DOMAIN>` does not load while `it-tools` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://it-tools:80/ \| head` |
