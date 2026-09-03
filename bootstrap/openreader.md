# OpenReader first-run

OpenReader runs on **periphery**. The docstore (SQLite + blobs) is a local HTPC volume (`openreader-docstore`). Caddy is `https://read.<DOMAIN>` (`openreader.` and `reader.` are aliases).

SeaweedFS port **8333** is **not** published. Uploads go through the app API on **3003**.

## 1. Secrets (existing Core)

If this site already ran `core.sh` before OpenReader existed, add the key in Komodo. Do not re-run bootstrap only for this.

1. Generate a secret: `openssl rand -hex 24`
2. Komodo → **Settings** → **Secrets** → **`OPENREADER_AUTH_SECRET`**. Mark it a secret.

New Core installs get the key from `core.sh` into `/etc/komodo/core.config.toml`.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **openreader** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **3003** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=openreader --format "table {{.Names}}\t{{.Status}}"
```

You want `openreader` **Up**.

## 3. Admin and TTS

Open **`https://read.<DOMAIN>`**. Create an account whose email is **`admin@<DOMAIN>`** — that address is `ADMIN_EMAILS`, so the **Settings → Admin** tab appears.

TTS is **not** catalogued. There is no Kokoro/GPU worker (Docker Desktop GPU is out of scope). Add an OpenAI-compatible provider under **Settings → Admin → Shared providers** (local or remote). Until that exists, upload and read still work; read-along audio does not.

Changing `OPENREADER_AUTH_SECRET` later signs everyone out.

## If it fails

| Symptom | What to do |
|---|---|
| `read.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:3003/ \| head` |
| Cookie / CSRF / redirect loop | `BASE_URL` must be `https://read.<DOMAIN>`. Redeploy **openreader** after the catalog pull |
| Uploads fail | Do not expose 8333. The catalog uses the app fallback on 3003 |
| No Admin tab | Sign in as `admin@<DOMAIN>` |
| No voices | Add a shared TTS provider in Admin. CUDA images are not in this catalog |
