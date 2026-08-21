# Remote Periphery — Layer 0

Komodo Core stays on the Core host. This machine runs **outbound Periphery** (default server name `periphery`) plus stacks from `stacks-periphery.toml`.

Override `CORE_SERVER` / `PERIPHERY_SERVER` (and `PERIPHERY_CONNECT_AS`) if this site does not use the defaults.

This catalog’s remote engine is Docker Desktop (WSL2 backend). Do not install docker-ce inside a user WSL distro.

## 1. Docker Desktop

```text
winget import -i windows\packages.json
```

Or install `Docker.DockerDesktop` alone. Enable WSL2 backend. Share the drive that will hold `DATA_ROOT` (Settings → Resources → File sharing).

## 2. Map Core DATA_ROOT

On Windows, map the Core host’s share (the same tree: `system/core/`, `system/periphery/`, `shared/`, `users/`) to a persistent drive letter or a folder Docker Desktop can bind. The HTPC SMB account SHOULD have read/write on `shared/`, `users/`, and `system/periphery/`, and MUST NOT have access to `system/core/` (Authelia, Vaultwarden, Pi-hole, WireGuard).

Set Komodo variable `DATA_ROOT` on the **periphery** server to that Docker-visible path. It must not be the laptop internal SSD.

Set `BACKUP_DRIVE` to the USB backup volume path as Docker Desktop sees it (Restic REST data). Not under `shared/media`.

## 3. Windows Firewall

Allow inbound TCP from the LAN (Caddy on Core) on the published ports:

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

Create `periphery.env` next to `bootstrap/periphery.compose.yaml`:

```text
COMPOSE_KOMODO_IMAGE_TAG=2
TZ=America/Los_Angeles
PERIPHERY_CORE_ADDRESS=ws://<CORE_LAN_IP>:9120
PERIPHERY_CONNECT_AS=periphery
PERIPHERY_ONBOARDING_KEY=<create in Komodo Settings → Onboarding, privileged if replacing keys>
PERIPHERY_ROOT_DIRECTORY=/etc/komodo
```

Use the same `PERIPHERY_CONNECT_AS` as `PERIPHERY_SERVER` (default `periphery`). `<CORE_LAN_IP>` is a runtime value, not something from git.

In Komodo UI, create an onboarding key and allow it to connect as that server name.

## 5. Start Periphery

```text
docker compose --env-file periphery.env -f periphery.compose.yaml up -d
```

Confirm the periphery server is connected in Komodo, then add `stacks/komodo/stacks-periphery.toml` to ResourceSync (or a second sync) and apply. Do not apply that file before the `periphery` server exists.

## 6. Restic REST htpasswd (optional file on USB)

If you use basic auth, write an htpasswd file on `BACKUP_DRIVE` (not in git). The restic-rest stack mounts `${BACKUP_DRIVE}/htpasswd`. Create it with `htpasswd` or `docker run --rm httpd:2 apache2-utils` equivalent, using `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` from Komodo.
