# Restic first-run

NAS **restic** (Core) writes snapshots of `${DATA_ROOT}` to Restic REST on mantle. The repository lives on the 4TB USB (`BACKUP_DRIVE`), not on the IronWolf and not under `shared/media`. REST listens on `SURFACE_UPSTREAM:8000`. There is no public Caddy vhost.

Secrets: `RESTIC_PASSWORD` (repo), `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` (HTTP basic). Optional `UPTIME_KUMA_PUSH_URL` after a Kuma Push monitor exists (`bootstrap/first-run/uptime-kuma.md`).

## 1. Wipe and share the USB (surface)

The disk is plugged in as **D:**. Existing files on it are discarded.

Elevated PowerShell on the surface console. A run **without** `-Wipe` only creates `D:\restic` and smoke-tests mantle’s `/mnt/d`; old files stay. To erase the disk:

```text
powershell -ExecutionPolicy Bypass -File bootstrap\surface\surface-backup-drive.ps1 -Wipe -ConfirmText ERASE
```

That GPT-formats disk **D:** as NTFS (`RESTIC`), creates `D:\restic`, and allows TCP 8000 on the Private profile. Then `wsl --shutdown` and reopen mantle so `/mnt/d` is the USB.

```text
powershell -ExecutionPolicy Bypass -File bootstrap\surface\surface-backup-drive.ps1
```

You want: `mantle can read /mnt/d/restic`. Attribute `BACKUP_DRIVE` is `D:` on Windows / `/mnt/d` in WSL (no trailing slash). Quadlets mount `${BACKUP_DRIVE}/restic` as `/data` (repo and `.htpasswd` live in that folder).

If the bind smoke test fails (`/mnt/d` missing): Windows shares **Fixed** drive letters into WSL, not Removable flash/SD. A USB HDD enclosure that Disk Management shows as a normal volume usually works after `wsl --shutdown`. Do not apply **restic-rest** until the smoke test passes. SMART for this disk is still the Windows collector (`bootstrap/first-run/scrutiny.md`).

## 2. Secrets and BACKUP_DRIVE (Core)

Commit and push this catalog after the WSL bind smoke test. Then on Core, set `BACKUP_DRIVE`, `RESTIC_PASSWORD`, `RESTIC_REST_PASSWORD`, and `RESTIC_REST_USER` (default `restic`) in `/etc/infra-core/site.env` (or re-run the secrets portion of `core.sh`). Existing secrets are kept.

Read the REST password when you need htpasswd (do not paste it into git):

```text
sudo awk -F= '/^RESTIC_REST_PASSWORD=/{gsub(/['\''"]/, "", $2); print $2}' /etc/infra-core/site.env
```

## 3. htpasswd on the USB (surface)

WSL Podman cannot bind a single file on `D:` (it becomes a directory; `:ro` then breaks `touch`). Put the password file **inside** the data folder: `D:\restic\.htpasswd`.

Stop **restic-rest** if it is already up. In Explorer, if `D:\htpasswd` is a **folder**, delete it.

Same user/password as `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD`. In PowerShell (output only — do not redirect onto D:):

```text
wsl -u pilot -- podman run --rm --entrypoint htpasswd httpd:2 -Bbn restic YOUR_RESTIC_REST_PASSWORD
```

Copy the one line (`restic:$2y$...`). Notepad → Save As `D:\restic\.htpasswd` (not `.txt`; encoding UTF-8 or ANSI). One line, no extra spaces.

The file stays on the USB, not in git.

## 4. Apply

Apply with `apply.sh`. **restic-rest** on mantle first, then **restic** on Core.

On mantle:

```text
podman ps --filter name=restic-rest --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You want `restic-rest` **Up** and `0.0.0.0:8000->8000/tcp`.

On Core:

```text
podman ps --filter name=restic --format "table {{.Names}}\t{{.Status}}"
podman logs -f restic
```

First start `restic init`s `...:8000/core` if the repo is empty, then `restic backup /data`. That is the whole `DATA_ROOT` tree (Vaultwarden, OpenCloud, media, …). The first snapshot can take hours. `stop_grace_period` is 6h so a re-apply does not SIGKILL a long backup. After each successful backup, `forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune`, then an optional Kuma ping.

From Core, after the first snapshot exists:

```text
podman exec restic restic snapshots
```

## 5. Uptime Kuma (optional)

Create a Push monitor, set `UPTIME_KUMA_PUSH_URL` to the edge URL (`http://127.0.0.1:3004/api/push/...` or the in-pod URL), re-apply **restic**. Empty skips the ping. Details: `bootstrap/first-run/uptime-kuma.md`.

## If it fails

| Symptom | What to do |
|---|---|
| `restic-rest` bind / `/mnt/d` | Smoke test in §1. `wsl --shutdown` after the wipe. Confirm Disk Management shows **D:** as Fixed |
| `touch: /htpasswd: Read-only file system` | Old bind-mounted a file as `:ro`. Use `D:\restic\.htpasswd` and the unit that only mounts `restic/` (see §3). Stop the stack, delete `D:\htpasswd` if it is a folder |
| `restic-rest` missing htpasswd | §3. File must be `D:\restic\.htpasswd`, not a directory named `htpasswd` |
| Client crash-loop `connection refused` / `:8000` | **restic-rest** must be Up before **restic**. Firewall TCP 8000 Private. From Core: `wget -S -O- --timeout=5 http://<SURFACE_UPSTREAM>:8000/` (401 is success) |
| `wrong password` / 401 on REST | `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` must match htpasswd. Re-apply **restic-rest** after rewriting the file |
| `Fatal: config file not found` on later runs | Wrong `BACKUP_DRIVE` or USB unplugged. Repo is `D:\restic\core` |
| Backup fills the 4TB disk | Retention is in `components/restic/backup.sh`. Media under `shared/` is included on purpose |
| Push monitor stays down | `uptime-kuma.md` §5 |

Leave **restic** off during an IronWolf data copy (`bootstrap/omv/ironwolf-migrate.md`). The USB is the backup target; the IronWolf is `DATA_ROOT`.
