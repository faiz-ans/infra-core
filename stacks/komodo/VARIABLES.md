# Komodo variable and secret keys

Values are **not** stored in this repository. Define these in Komodo (UI Variables, or Core/Periphery `[secrets]` written by bootstrap).

Mark items tagged **secret** as secrets in Komodo.

## Site

| Key | Secret | Used by |
|---|---|---|
| `CATALOG_REPO` | | Informational. Stack `repo` in ResourceSync TOML is the catalog literal `faiz-ans/infra-core` |
| `CORE_SERVER` | | Bootstrap `connect_as` / first server. Must match TOML `server = "core"` |
| `PERIPHERY_SERVER` | | Remote Periphery `connect_as`. Must match TOML `server = "periphery"` |
| `DOMAIN` | | Caddy, Authelia, Pi-hole, Homepage, Vaultwarden public URL |
| `TZ` | | Most containers |
| `NAS_LAN_IP` | | Pi-hole wildcard, Homepage/Prometheus scrape of NAS-published ports |
| `HTPC_UPSTREAM` | | Caddy upstreams, Homepage HTPC widgets, NAS restic client |
| `DATA_ROOT` | | Per-server. Core: OMV uuid mount or `/srv/core`. Periphery: Docker Desktop-visible share |
| `BACKUP_DRIVE` | | HTPC Restic REST data directory |
| `PUID` | | linuxserver images on both hosts |
| `PGID` | | linuxserver images on both hosts |

## Auth and edge

| Key | Secret | Used by |
|---|---|---|
| `AUTHELIA_JWT_SECRET` | secret | Authelia |
| `AUTHELIA_SESSION_SECRET` | secret | Authelia |
| `AUTHELIA_STORAGE_ENCRYPTION_KEY` | secret | Authelia |
| `WG_HOST` | | wg-easy endpoint (hostname or IP clients dial) |
| `WG_PASSWORD_HASH` | secret | wg-easy UI |

Authelia user hashes live in `${DATA_ROOT}/system/authelia/users.yml` on the NAS (written by bootstrap), not in Komodo.

## Vaultwarden

| Key | Secret | Used by |
|---|---|---|
| `VAULTWARDEN_ADMIN_TOKEN` | secret | Vaultwarden `/admin` |
| `SIGNUPS_ALLOWED` | | Vaultwarden (`false` after first user) |

## Backup

| Key | Secret | Used by |
|---|---|---|
| `RESTIC_PASSWORD` | secret | Repo encryption (NAS client) |
| `RESTIC_REST_USER` | | REST server basic auth |
| `RESTIC_REST_PASSWORD` | secret | REST server basic auth |

## Homepage widget keys (optional until apps are configured)

| Key | Secret |
|---|---|
| `HOMEPAGE_VAR_PIHOLE_TOKEN` | secret |
| `HOMEPAGE_VAR_JELLYFIN_KEY` | secret |
| `HOMEPAGE_VAR_SONARR_KEY` | secret |
| `HOMEPAGE_VAR_RADARR_KEY` | secret |
| `HOMEPAGE_VAR_PROWLARR_KEY` | secret |
| `HOMEPAGE_VAR_QBIT_USERNAME` | |
| `HOMEPAGE_VAR_QBIT_PASSWORD` | secret |
| `HOMEPAGE_VAR_GRAFANA_KEY` | secret |

`HOMEPAGE_VAR_DOMAIN` and `HOMEPAGE_VAR_HTPC_UPSTREAM` are **mapped from** `DOMAIN` and `HTPC_UPSTREAM` in the Homepage stack environment. Do not duplicate live values in git.

## HTPC apps

| Key | Secret | Used by |
|---|---|---|
| `GRAFANA_ADMIN_PASSWORD` | secret | Grafana |
| `NEXTCLOUD_ADMIN_USER` | | Nextcloud first-run |
| `NEXTCLOUD_ADMIN_PASSWORD` | secret | Nextcloud first-run |
| `SMB_USERNAME` | | Optional CIFS fallback (not required if Desktop bind-mounts `DATA_ROOT`) |
| `SMB_PASSWORD` | secret | Optional CIFS fallback |
