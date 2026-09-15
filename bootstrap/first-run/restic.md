# Restic first-run

NAS **restic** (Core) writes snapshots of `${DATA_ROOT}` to Restic REST on the HTPC. The repository lives on the 4TB USB (`BACKUP_DRIVE`), not on the IronWolf and not under `shared/media`. REST listens on `HTPC_UPSTREAM:8000`. There is no public Caddy vhost.

Secrets: `RESTIC_PASSWORD` (repo), `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` (HTTP basic). Optional `UPTIME_KUMA_PUSH_URL` after a Kuma Push monitor exists (`bootstrap/first-run/uptime-kuma.md`).

## 1. Wipe and share the USB (HTPC)

The disk is plugged in as **D:**. Existing files on it are discarded.

Elevated PowerShell on the HTPC console. A run **without** `-Wipe` only creates `D:\restic` and smoke-tests Docker; old files stay. To erase the disk:

```text
powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1 -Wipe -ConfirmText ERASE
```

That GPT-formats disk **D:** as NTFS (`RESTIC`), creates `D:\restic`, and allows TCP 8000 on the Private profile. Then **fully quit and restart Docker Desktop** so WSL2 sees the letter.

```text
powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1
```

You want: `Docker can read D:/restic`. Komodo `BACKUP_DRIVE` is `D:` (no trailing slash). Compose mounts `${BACKUP_DRIVE}/restic` and `${BACKUP_DRIVE}/htpasswd`.

If the bind smoke test fails (`/run/desktop/mnt/host/d` missing): Docker Desktop shares **Fixed** drive letters, not Removable flash/SD. A USB HDD enclosure that Disk Management shows as a normal volume usually works after a Desktop restart. Do not Deploy **restic-rest** until the smoke test passes. SMART for this disk is still the Windows collector (`bootstrap/first-run/scrutiny.md`).

## 2. Secrets and BACKUP_DRIVE (Core)

Commit and push this catalog after the Docker bind smoke test (`deploy = true` will let ResourceSync start the stacks; if that happens before htpasswd exists, **restic-rest** fails until you Redeploy). Then on Core:

```text
sudo bash bootstrap/komodo/sync-komodo-secrets.sh
cd /etc/komodo/bootstrap && sudo docker compose --env-file compose.env -f compose.yaml up -d
```

Prompt `BACKUP_DRIVE` as `D:`. New keys: `RESTIC_PASSWORD`, `RESTIC_REST_PASSWORD` (generated); `RESTIC_REST_USER` defaults to `restic`. Existing secrets are kept.

Read the REST password when you need htpasswd (do not paste it into git):

```text
sudo awk -F\" '/^RESTIC_REST_PASSWORD /{print $2}' /etc/komodo/core.config.toml
```

## 3. htpasswd on the USB (HTPC)

Same user/password as Komodo. Elevated PowerShell:

```text
powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1 -RestUser restic -RestPassword '<RESTIC_REST_PASSWORD>'
```

That writes `D:\htpasswd` (bcrypt). The file stays on the USB, not in git.

## 4. Deploy

Wait for ResourceSync. Komodo → **restic-rest** → **Deploy** first. Then **restic**.

On the HTPC:

```text
docker ps --filter name=restic-rest --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You want `restic-rest` **Up** and `0.0.0.0:8000->8000/tcp`.

On Core:

```text
docker ps --filter name=restic --format "table {{.Names}}\t{{.Status}}"
docker logs -f restic
```

First start `restic init`s `...:8000/core` if the repo is empty, then `restic backup /data`. That is the whole `DATA_ROOT` tree (Vaultwarden, OpenCloud, media, …). The first snapshot can take hours. `stop_grace_period` is 6h so a Redeploy does not SIGKILL a long backup. After each successful backup, `forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune`, then an optional Kuma ping.

From Core, after the first snapshot exists:

```text
docker exec restic restic snapshots
```

## 5. Uptime Kuma (optional)

Create a Push monitor, set `UPTIME_KUMA_PUSH_URL` to the edge URL (`http://uptime-kuma:3001/api/push/...`), Redeploy **restic**. Empty skips the ping. Details: `bootstrap/first-run/uptime-kuma.md`.

## If it fails

| Symptom | What to do |
|---|---|
| `restic-rest` bind / `/run/desktop/mnt/host/d` | Smoke test in §1. Restart Docker Desktop after the wipe. Confirm Disk Management shows **D:** as Fixed |
| `restic-rest` missing `/htpasswd` | §3. The mount is a **file** `D:\htpasswd`, not a directory |
| Client crash-loop `connection refused` / `:8000` | **restic-rest** must be Up before **restic**. Firewall TCP 8000 Private. From Core: `wget -S -O- --timeout=5 http://<HTPC_UPSTREAM>:8000/` (401 is success) |
| `wrong password` / 401 on REST | `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` must match htpasswd. Redeploy **restic-rest** after rewriting the file |
| `Fatal: config file not found` on later runs | Wrong `BACKUP_DRIVE` or USB unplugged. Repo is `D:\restic\core` |
| Backup fills the 4TB disk | Retention is in `stacks/platform/restic/backup.sh`. Media under `shared/` is included on purpose |
| Push monitor stays down | `uptime-kuma.md` §5 |

Leave **restic** off during an IronWolf data copy (`bootstrap/omv/ironwolf-migrate.md`). The USB is the backup target; the IronWolf is `DATA_ROOT`.
