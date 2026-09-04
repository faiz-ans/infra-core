# LibreTranslate first-run

LibreTranslate runs on **periphery**. Argos models are a local HTPC volume (`libretranslate-models`), not NFS. Caddy is `https://translate.<DOMAIN>` (`libretranslate.` is an alias). The vhost is Authelia forward-auth (`users` — **faiz** and **diana**).

No Komodo secret.

## 1. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **libretranslate** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **5000** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=libretranslate --format "table {{.Names}}\t{{.Status}}"
docker logs -f libretranslate
```

First start **downloads language models** and can take several minutes (a few GB). Wait until the healthcheck is healthy before opening the URL. Subsequent starts reuse `libretranslate-models`.

## 2. Use

Open **`https://translate.<DOMAIN>`**. The UI and `/translate` API are the same origin.

To load fewer languages later, set `LT_LOAD_ONLY` (for example `en,es,fr,de`) in the stack environment and Redeploy. That is not in the catalog by default.

## If it fails

| Symptom | What to do |
|---|---|
| `translate.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:5000/ \| head` |
| Still starting / no UI | Watch logs until models finish downloading. Do not treat a slow first pull as a crash |
| Models download again after Redeploy | Confirm named volume `libretranslate-models` is still attached |
