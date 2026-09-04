# BentoPDF first-run

BentoPDF runs on **Core** (edge network). It is a client-side WASM PDF toolkit; files never leave the browser. Caddy is `https://pdf.<DOMAIN>` (`bentopdf.` is an alias). The vhost is Authelia forward-auth (`users` — **faiz** and **diana**).

No Komodo secret. No data directory.

## 1. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **bentopdf** → **Deploy**. Redeploy **caddy** and **homepage**.

On Core:

```text
docker ps --filter name=bentopdf --format "table {{.Names}}\t{{.Status}}"
```

You want `bentopdf` **Up**. It must **not** publish 8080 on the LAN.

## 2. Use

Open **`https://pdf.<DOMAIN>`**. Tools run in the browser. HTTPS (`tls internal`) is required for some conversions.

## If it fails

| Symptom | What to do |
|---|---|
| `pdf.<DOMAIN>` does not load while `bentopdf` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://bentopdf:8080/ \| head` |
