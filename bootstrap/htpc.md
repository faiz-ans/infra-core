# HTPC (Docker Desktop) — Layer 0

Komodo Core stays on the Pi. This host only runs **outbound Periphery** as server `htpc` plus the HTPC stacks from ResourceSync.

Do not install docker-ce inside a user WSL distro. Use Docker Desktop (WSL2 backend).

## 1. Docker Desktop

```text
winget import -i windows\packages.json
```

Or install `Docker.DockerDesktop` alone. Enable WSL2 backend. Share the drive that will hold `DATA_ROOT` (Settings → Resources → File sharing).

## 2. Map OMV as DATA_ROOT

On Windows, map the OMV SMB share (the same tree as the NAS `DATA_ROOT`: `system/`, `shared/`, `users/`) to a persistent drive letter or a folder Docker Desktop can bind.

Set Komodo variable `DATA_ROOT` on server `htpc` to that Docker-visible path (for example a `/run/desktop/mnt/host/...` path or the path Compose accepts for the mapped drive). It must not be the laptop internal SSD.

Set `BACKUP_DRIVE` to the 4TB USB volume path as Docker Desktop sees it (Restic REST data). Not under `shared/media`.

## 3. Windows Firewall

Allow inbound TCP from the LAN (Caddy on the NAS) on the published ports:

| Port | Stack |
|---|---|
| 8096 | Jellyfin |
| 8123 | Home Assistant |
| 8080 | Nextcloud |
| 8081 | qBittorrent |
| 8989 | Sonarr |
| 7878 | Radarr |
| 9696 | Prowlarr |
| 3000 | Grafana |
| 9090 | Prometheus (optional) |
| 8000 | Restic REST |

## 4. Periphery env (write on the box, do not commit)

Create `htpc-periphery.env` next to `bootstrap/htpc-periphery.compose.yaml`:

```text
COMPOSE_KOMODO_IMAGE_TAG=2
TZ=Etc/UTC
PERIPHERY_CORE_ADDRESS=ws://<NAS_LAN_IP>:9120
PERIPHERY_ONBOARDING_KEY=<create in Komodo Settings → Onboarding, privileged if replacing keys>
PERIPHERY_ROOT_DIRECTORY=/etc/komodo
```

`<NAS_LAN_IP>` is a runtime value on this host, not something from git.

In Komodo UI, create an onboarding key and allow it to connect as **`htpc`**.

## 5. Start Periphery

```text
docker compose --env-file htpc-periphery.env -f htpc-periphery.compose.yaml up -d
```

Confirm server `htpc` is connected in Komodo, then apply ResourceSync for `stacks/komodo/stacks-htpc.toml`.

## 6. Restic REST htpasswd (optional file on USB)

If you use basic auth, write an htpasswd file on `BACKUP_DRIVE` (not in git). The restic-rest stack mounts `${BACKUP_DRIVE}/htpasswd`. Create it with `htpasswd` or `docker run --rm httpd:2 apache2-utils` equivalent, using `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` from Komodo.
