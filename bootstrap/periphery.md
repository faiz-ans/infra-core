# Remote Periphery — Layer 0

Komodo Core stays on the Core host. This machine runs **outbound Periphery** (default server name `periphery`) plus stacks from `stacks-periphery.toml`.

Override `CORE_SERVER` / `PERIPHERY_SERVER` (and `PERIPHERY_CONNECT_AS`) if this site does not use the defaults.

This catalog’s remote engine is Docker Desktop (WSL2 backend). Do not install docker-ce inside a user WSL distro.

## 1. Docker Desktop

```text
winget import -i windows\packages.json
```

Or install `Docker.DockerDesktop` alone. Enable WSL2 backend. Share only the USB volume used as `BACKUP_DRIVE` (Settings → Resources → File sharing). Do not share an SMB-mapped `Z:` (or similar) for app data.

## 2. NAS data: pick a transport per stack

Workload compose is transport-agnostic. Komodo `file_paths` chooses one file (never both):

| File | When | Komodo env |
|---|---|---|
| `compose.yaml` | Local disk, or a host mount of NFS/SMB/CIFS at `DATA_ROOT` | `DATA_ROOT` |
| `compose.nfs.yaml` | Docker engine mounts OMV NFS itself (this HTPC) | `NAS_LAN_IP`, `NFS_EXPORT` |

This site’s `stacks-periphery.toml` uses `compose.nfs.yaml` for Jellyfin, Arr, qBittorrent, and Nextcloud. Follow `bootstrap/omv-nfs.md`, then set `NAS_LAN_IP` and `NFS_EXPORT=/data` (or `/<shared-folder-name>`). Do not set those stacks’ `DATA_ROOT` to `Z:`.

Home Assistant’s HTPC file is also named `compose.nfs.yaml`, but `/config` is a **local Docker volume** plus a bind of `configuration.yaml` (NFS file overlays break `trusted_proxies`). `.storage` is not on DATA_ROOT.

A future single-host or Linux engine can point a stack at `compose.yaml` and a local/host `DATA_ROOT`.

SMB stays for Explorer/Finder. Map those shares as you like; they are not required for `compose.nfs.yaml`.

Set `BACKUP_DRIVE` to the USB backup volume path as Docker Desktop sees it (Restic REST data). Not under `shared/media`.

## 3. Windows Firewall

Allow inbound TCP from the LAN (Caddy on Core) on the published ports:

| Port | Stack |
|---|---|
| 53/tcp+udp | Pi-hole (bind `HTPC_UPSTREAM` only) |
| 8083 | Pi-hole admin (`dns2.${DOMAIN}` via Caddy; LAN fallback if Core is up) |
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

Router DHCP DNS: Core `NAS_LAN_IP` first, then `HTPC_UPSTREAM`. Do not add a public resolver as a third DHCP DNS. After deploy, Teleporter (or copy) Gravity from the Core Pi-hole so both filter the same. Windows may already use :53 (ICS / another DNS); if the stack cannot bind, stop that listener.

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
