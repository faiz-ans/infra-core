# OpenReader first-run

OpenReader runs on **mantle**. The docstore (SQLite + blobs) is a local WSL volume (`openreader-docstore`). Caddy is `https://read.<DOMAIN>` (`openreader.` and `reader.` are aliases).

SeaweedFS port **8333** is **not** published. Uploads go through the app API on **3003**.

## 1. Secrets (existing Core)

If this site already ran `core.sh` before OpenReader existed, add the key in `/etc/materia/site.env`. Do not re-run bootstrap only for this.

1. Generate a secret: `openssl rand -hex 24`
2. Set **`OPENREADER_AUTH_SECRET`** in `/etc/materia/site.env` (and sops attributes).

New Core installs get the key from `core.sh` into `/etc/materia/core.config.toml`.

## 2. Deploy

Commit and push to the catalog git origin. Wait for Materia, then re-apply **caddy** and **homepage**.

On mantle, allow Windows Firewall TCP **3003** from the LAN (Caddy). See `bootstrap/mantle/README.md`.

```text
podman ps --filter name=openreader --format "table {{.Names}}\t{{.Status}}"
```

You want `openreader` **Up**.

## 3. Admin and TTS

Open **`https://read.<DOMAIN>`**. Create an account whose email is **`admin@<DOMAIN>`** — that address is `ADMIN_EMAILS`, so the **Settings → Admin** tab appears.

TTS is **not** catalogued. There is no Kokoro/GPU worker (WSL Podman GPU is out of scope). Add an OpenAI-compatible provider under **Settings → Admin → Shared providers** (local or remote). Until that exists, upload and read still work; read-along audio does not.

Changing `OPENREADER_AUTH_SECRET` later signs everyone out.

## If it fails

| Symptom | What to do |
|---|---|
| `read.<DOMAIN>` does not load while the container is Up | re-apply (Materia / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=10 http://<SURFACE_UPSTREAM>:3003/ \| head` |
| Cookie / CSRF / redirect loop | `BASE_URL` must be `https://read.<DOMAIN>`. re-apply (Materia / systemd) **openreader** after the catalog pull |
| Uploads fail | Do not expose 8333. The catalog uses the app fallback on 3003 |
| No Admin tab | Sign in as `admin@<DOMAIN>` |
| No voices | Add a shared TTS provider in Admin. CUDA images are not in this catalog |
