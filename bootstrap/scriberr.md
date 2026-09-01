# Scriberr first-run

Scriberr runs on **periphery**. SQLite, uploads, and Whisper models are local HTPC volumes (not NFS). Caddy is `https://scribe.<DOMAIN>` (`transcribe.` and `scriberr.` are aliases).

No Komodo secret. The first browser visit creates the admin. JWT material is generated inside the data volume.

## 1. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **scriberr** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall TCP **8085** from the LAN (Caddy). See `bootstrap/periphery.md`.

```text
docker ps --filter name=scriberr --format "table {{.Names}}\t{{.Status}}"
docker logs -f scriberr
```

First start **downloads models** and can take several minutes. Wait for `Scriberr is ready` before opening the URL. Subsequent starts are much faster.

If Komodo shows Periphery **Not OK** and the Scriberr container is Up, that is the Docker LAN-overlap failure (not Scriberr itself). Fix it on the HTPC with `bootstrap/periphery.md` §7 **before** Redeploy. Windows can still reach Core; the Periphery container cannot. New HTPC sites apply Engine JSON in §1 so this does not happen.

## 2. Admin

Open **`https://scribe.<DOMAIN>`**. Create the household admin in the setup wizard.

Speaker diarization and optional Ollama/OpenAI chat are configured in the app UI, not in this catalog. CUDA images are not in the catalog (Docker Desktop GPU is out of scope).

## If it fails

| Symptom | What to do |
|---|---|
| `scribe.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:8085/ \| head` |
| Still starting / no UI | Watch logs until `Scriberr is ready`. Do not treat a slow first pull as a crash |
| SQLite / permission denied | Confirm Komodo `PUID`/`PGID` match the HTPC. Named volumes `scriberr-data` and `scriberr-whisperx` |
| Unable to load audio stream | Caddy must be HTTPS (`tls internal`). Do not set `SECURE_COOKIES=false` |
| CORS / blocked browser request | `ALLOWED_ORIGINS` must include the hostname you used. Redeploy **scriberr** after the catalog pull |
