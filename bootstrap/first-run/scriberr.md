# Scriberr first-run

Scriberr runs on **mantle**. SQLite, uploads, and Whisper models are local WSL volumes (not NFS). Caddy is `https://scribe.<DOMAIN>` (`transcribe.` and `scriberr.` are aliases).

No attribute. The first browser visit creates the admin. JWT material is generated inside the data volume.

## 1. Deploy

Commit and push to the catalog git origin. Wait for Materia, then re-apply **caddy** and **homepage**.

On mantle, allow Windows Firewall TCP **8085** from the LAN (Caddy). See `bootstrap/mantle/README.md`.

```text
podman ps --filter name=scriberr --format "table {{.Names}}\t{{.Status}}"
podman logs -f scriberr
```

First CUDA start **downloads NVIDIA models before it listens** (Canary alone is ~6 GiB). Quadlet/Homepage “running” is not ready. Wait for the log line `Scriberr is ready` `url=http://0.0.0.0:8080`. That can take 15–30 minutes and tens of GiB **once**; then `C:` should stop falling. Stopping mid-download makes the next start eat disk again. Open **`https://voice.<DOMAIN>`** (not `scribe.`).

If Scriberr is Up but mantle cannot reach Core, see `bootstrap/mantle/README.md` before re-apply. Windows can still reach Core while WSL cannot.

## 2. Admin

Open **`https://voice.<DOMAIN>`**. Create the household admin in the setup wizard.

Speaker diarization and optional Ollama/OpenAI chat are configured in the app UI, not in this catalog. The catalog uses **`scriberr-cuda:latest`** (RTX 20-series). That image is ~9 GiB. `poll_for_updates` is off and the Quadlet pull policy is `missing` so a re-apply (Materia / systemd) does not pull another copy if the image is already on surface. Do not force-pull this image unless you intend to download ~9 GiB again. WSL Podman GPU must be on (`bootstrap/mantle/README.md`).

If this site previously ran the CPU image, wipe the Whisper env volume once so CUDA deps reinstall:

```text
podman stop scriberr
podman volume rm scriberr-whisperx
```

Then re-apply (Materia / systemd) **scriberr**. Keep `scriberr-data` (transcripts / admin).

## If it fails

| Symptom | What to do |
|---|---|
| `scribe.<DOMAIN>` does not load while the container is Up | re-apply (Materia / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=10 http://<SURFACE_UPSTREAM>:8085/ \| head` |
| Homepage green but browser blank | Container is running; HTTP is not. Wait for `Scriberr is ready` in logs. After this catalog’s healthcheck is live, Homepage should stay down until curl to :8080 works. |
| SQLite `readonly database (8)` | `scriberr-cuda` runs as UID **10001** (UID 1000 is `ubuntu` in the image). Household `PUID=1000` cannot write the DB. Stop the container, `podman run --rm -v scriberr-data:/data alpine chown -R 10001:10001 /data`, re-apply (Materia / systemd) **scriberr**. Do not override this stack’s PUID from attributes. |
| CUDA / no GPU | WSL Podman → Resources → GPU. `podman exec scriberr nvidia-smi` |
| Whisper env broken after CPU→CUDA | Remove `scriberr-whisperx` (above), re-apply (Materia / systemd) |
| Unable to load audio stream | Caddy must be HTTPS (`tls internal`). Do not set `SECURE_COOKIES=false` |
| CORS / blocked browser request | `ALLOWED_ORIGINS` must include the hostname you used. re-apply (Materia / systemd) **scriberr** after the catalog pull |
