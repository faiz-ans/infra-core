# Remote Periphery — Layer 0

Komodo Core stays on the Core host. This machine runs **outbound Periphery** (default server name `periphery`) plus stacks from `stacks-periphery.toml`.

Override `CORE_SERVER` / `PERIPHERY_SERVER` (and `PERIPHERY_CONNECT_AS`) if this site does not use the defaults.

This catalog’s remote engine is Docker Desktop (WSL2 backend). Do not install docker-ce inside a user WSL distro.

## 1. Docker Desktop

```text
winget import -i windows\packages.json
```

Or install `Docker.DockerDesktop` alone. Enable WSL2 backend. Share only the USB volume used as `BACKUP_DRIVE` (Settings → Resources → File sharing). Do not share an SMB-mapped `Z:` (or similar) for app data.

### Engine JSON (required before ResourceSync)

Each Komodo stack is its own Compose project and gets a Docker bridge. Factory pools are `/16`s in `172.18.0.0`–`172.31.0.0` (~12 user networks). The next project is assigned `192.168.0.0/16`, which includes Core. Windows can still reach the NAS; every container, including Periphery, times out and Komodo shows **Not OK**.

Do this **once**, after Desktop is installed and **before** `stacks-periphery.toml` is applied (and before you grow past ~12 HTPC stacks on an existing site):

```text
powershell -ExecutionPolicy Bypass -File bootstrap/periphery-docker-engine.ps1
```

That merges [`windows/docker-engine.json`](../windows/docker-engine.json) into `%USERPROFILE%\.docker\daemon.json` and leaves other Engine keys alone. Then **restart Docker Desktop**.

Alternatively: Settings → **Docker Engine** → paste the `default-address-pools` object from that file → Apply & restart.

```json
{
  "default-address-pools": [
    { "base": "10.200.0.0/16", "size": 24 }
  ]
}
```

`10.200.0.0/16` as `/24`s is 256 networks and does not overlap this catalog’s usual LAN (`192.168.1.0/24`) or existing `172.x` bridges. Core-only sites skip this. If Periphery is already **Not OK**, §7.

## 2. NAS data: pick a transport per stack

Workload compose is transport-agnostic. Komodo `file_paths` chooses one file (never both):

| File | When | Komodo env |
|---|---|---|
| `compose.yaml` | Local disk, or a host mount of NFS/SMB/CIFS at `DATA_ROOT` | `DATA_ROOT` |
| `compose.nfs.yaml` | Docker engine mounts OMV NFS itself (this HTPC) | `NAS_LAN_IP`, `NFS_EXPORT`, `NFS_USERS` (Immich) |

This site’s `stacks-periphery.toml` uses `compose.nfs.yaml` for Jellyfin, Arr, qBittorrent, Immich, and Frigate. Follow `bootstrap/omv-nfs.md`, then set `NAS_LAN_IP`, `NFS_EXPORT=/shared`, and `NFS_USERS=/users`. Do not set those stacks’ `DATA_ROOT` to `Z:`.

Home Assistant’s HTPC file is also named `compose.nfs.yaml`, but `/config` is a **local Docker volume**. `trusted_proxies` is written into that volume at start (`ensure-http/`); do not bind-mount `configuration.yaml` (Docker Desktop drops single-file binds, which produces Caddy 400s). `.storage` is not on DATA_ROOT.

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
| 5055 | Seerr (`request.${DOMAIN}` via Caddy) |
| 8123 | Home Assistant |
| 2283 | Immich (`photos.${DOMAIN}` via Caddy) |
| 9980 | Collabora (`office.${DOMAIN}` via Caddy) |
| 8081 | qBittorrent |
| 8989 | Sonarr |
| 7878 | Radarr |
| 9696 | Prowlarr |
| 3000 | Grafana |
| 9090 | Prometheus (optional) |
| 8000 | Restic REST |
| 8015 | Adventure Log (`travel.${DOMAIN}` via Caddy) |
| 8085 | Scriberr (`scribe.${DOMAIN}` via Caddy) |
| 3313 | Transmute (`convert.${DOMAIN}` via Caddy) |
| 5000 | LibreTranslate (`translate.${DOMAIN}` via Caddy) |
| 3003 | OpenReader (`read.${DOMAIN}` via Caddy) |
| 5678 | n8n (`flow.${DOMAIN}` via Caddy) |
| 61208 | Glances (`glances2.${DOMAIN}` via Caddy; Homepage host stats) |
| 8971 | Frigate UI (`cams.${DOMAIN}` via Caddy) |
| 8554 | Frigate RTSP restream (LAN; not Caddy) |
| 8555/tcp+udp | Frigate WebRTC (LAN; not Caddy) |
| 1883 | Frigate Mosquitto (Home Assistant; not Caddy) |

Router DHCP DNS: Core `NAS_LAN_IP` first, then `HTPC_UPSTREAM`. Do not add a public resolver as a third DHCP DNS. Each Pi-hole fetches its own Gravity. Windows may already use :53 (ICS / another DNS); if the stack cannot bind, stop that listener.

If Edge and `curl` work but Firefox says it **can’t find** `*.home.lan` (no certificate warning): Pi-hole’s IPv4-only `address=/home.lan/…` answers **AAAA with NXDOMAIN**. Firefox follows RFC 4074 and then never queries A. Edge still tries A. Cached A records keep Homepage (and the occasional other tab) alive.

```text
nslookup -type=AAAA cloud.home.lan
```

NXDOMAIN is the bug.

Immediate: Firefox `about:config` → `network.dns.disableIPv6` = `true`, then `about:networking#dns` → Clear DNS cache.

Lasting: Redeploy **pihole** and **pihole-periphery** after the catalog adds `local=/${DOMAIN}/` so AAAA is empty NODATA.

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

Confirm the periphery server is connected in Komodo, then add `stacks/komodo/stacks-periphery.toml` to ResourceSync (or a second sync) and apply. Do not apply that file before the `periphery` server exists, and do not apply it before §1 Engine JSON. ResourceSync stack names are global; the HTPC Pi-hole is `pihole-periphery` so it does not collide with Core `pihole`.

## 6. Restic REST htpasswd (optional file on USB)

If you use basic auth, write an htpasswd file on `BACKUP_DRIVE` (not in git). The restic-rest stack mounts `${BACKUP_DRIVE}/htpasswd`. Create it with `htpasswd` or `docker run --rm httpd:2 apache2-utils` equivalent, using `RESTIC_REST_USER` / `RESTIC_REST_PASSWORD` from Komodo.

## 7. Recover Periphery if Engine JSON was skipped

If Komodo already shows Periphery **Not OK** and Windows `wget` to Core still works, a Compose network is sitting on `192.168.0.0/16`. Komodo cannot fix that. On the HTPC:

```text
docker network inspect $(docker network ls -q) --format "{{.Name}}: {{range .IPAM.Config}}{{.Subnet}}{{end}}"
```

Any subnet in `192.168.0.0/16` is the problem (often `<stack>_default` for the last stack you applied).

```text
docker stop scriberr
docker rm scriberr
docker network rm scriberr_default
```

Use the name `inspect` printed. Then do §1 Engine JSON (script or Settings) and restart Docker Desktop. Recreate Periphery from the folder that has `periphery.env`:

```text
docker compose --env-file periphery.env -f periphery.compose.yaml up -d
```

Confirm `docker exec` into the Periphery container can `wget --timeout=5 http://<CORE_LAN_IP>:9120/`. Komodo should show **OK**. Then Deploy the last stack again.

Do not `docker network prune` unless you have just listed networks and know what you are removing. Named volumes survive `rm` of the container and network.
