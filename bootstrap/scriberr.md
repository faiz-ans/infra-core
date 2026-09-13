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

Speaker diarization and optional Ollama/OpenAI chat are configured in the app UI, not in this catalog. The catalog uses **`scriberr-cuda:latest`** (RTX 20-series). That image is ~9 GiB. `poll_for_updates` is off and compose `pull_policy` is `missing` so a Redeploy does not pull another copy if the image is already on the HTPC. Do not Komodo **Pull** this stack unless you intend to download ~9 GiB again. Docker Desktop GPU must be on (`bootstrap/periphery.md`).

If this site previously ran the CPU image, wipe the Whisper env volume once so CUDA deps reinstall:

```text
docker stop scriberr
docker volume rm scriberr-whisperx
```

Then Redeploy **scriberr**. Keep `scriberr-data` (transcripts / admin).

## If it fails

| Symptom | What to do |
|---|---|
| `scribe.<DOMAIN>` does not load while the container is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:8085/ \| head` |
| Still starting / no UI | Watch logs until `Scriberr is ready`. Do not treat a slow first pull as a crash |
| SQLite `readonly database (8)` | `scriberr-cuda` runs as UID **10001** (UID 1000 is `ubuntu` in the image). Household `PUID=1000` cannot write the DB. Stop the container, `docker run --rm -v scriberr-data:/data alpine chown -R 10001:10001 /data`, Redeploy **scriberr**. Do not set this stack’s PUID from Komodo. |
| CUDA / no GPU | Docker Desktop → Resources → GPU. `docker exec scriberr nvidia-smi` |
| Whisper env broken after CPU→CUDA | Remove `scriberr-whisperx` (above), Redeploy |
| Unable to load audio stream | Caddy must be HTTPS (`tls internal`). Do not set `SECURE_COOKIES=false` |
| CORS / blocked browser request | `ALLOWED_ORIGINS` must include the hostname you used. Redeploy **scriberr** after the catalog pull |
