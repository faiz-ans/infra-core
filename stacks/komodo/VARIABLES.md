# Komodo variable and secret keys

Values are **not** stored in this repository. Define these in Komodo (UI Variables, or Core/Periphery `[secrets]` written by bootstrap).

Mark items tagged **secret** as secrets in Komodo.

## Site

| Key | Secret | Used by |
|---|---|---|
| `CATALOG_REPO` | | Informational. Stack `repo` in ResourceSync TOML is the catalog path `faiz-ans/infra-core` (Gitea origin; GitHub is a push mirror). After Gitea exists, Komodo `git_provider` is `gitea:3000` (see `bootstrap/gitea.md`). |
| `CORE_SERVER` | | Bootstrap `connect_as` / first server. Must match TOML `server = "core"` |
| `PERIPHERY_SERVER` | | Remote Periphery `connect_as`. Must match TOML `server = "periphery"` |
| `DOMAIN` | | Caddy, Authelia, Pi-hole, Homepage, Vaultwarden public URL |
| `TZ` | | Most containers |
| `NAS_LAN_IP` | | Pi-hole wildcard (`*.DOMAIN` → Caddy), Homepage/Prometheus scrape, periphery NFS `addr=` |
| `HTPC_UPSTREAM` | | Caddy upstreams, Homepage HTPC widgets, NAS restic client |
| `DATA_ROOT` | | Bind-mount compose (`compose.yaml`). Core app state is `${DATA_ROOT}/system/<app>`. Periphery `/config` is a local volume; household data uses `${DATA_ROOT}/shared` and `${DATA_ROOT}/users`. A stack that uses `compose.nfs.yaml` does not set this. |
| `NFS_EXPORT` | | Docker-NFS path of the OMV `shared` share (`/shared`). Used as `:${NFS_EXPORT}/media` etc. No quotes, not a drive letter |
| `NFS_USERS` | | Docker-NFS path of the OMV `users` share (`/users`). Immich External Libraries. No quotes |
| `BACKUP_DRIVE` | | HTPC Restic REST data directory |
| `PUID` | | linuxserver images on both hosts |
| `PGID` | | linuxserver images on both hosts |

## Auth and edge

| Key | Secret | Used by |
|---|---|---|
| `AUTHELIA_JWT_SECRET` | secret | Authelia |
| `AUTHELIA_SESSION_SECRET` | secret | Authelia |
| `AUTHELIA_STORAGE_ENCRYPTION_KEY` | secret | Authelia |
| `WG_HOST` | | wg-easy INIT_HOST. Public DNS name that resolves off-LAN to the WAN IPv4 (Dynamic DNS if the WAN moves). Not a LAN-only name. |
| `WG_UI_PASSWORD` | secret | wg-easy v15 admin password (plaintext; used only at first start) |

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
| `HOMEPAGE_VAR_WGEASY_PASSWORD` | secret |

`HOMEPAGE_VAR_WGEASY_PASSWORD` is the live wg-easy `wg-admin` login (not `WG_UI_PASSWORD` unless you never changed it). wg-easy 2FA must stay off for the widget API.

`HOMEPAGE_VAR_DOMAIN` and `HOMEPAGE_VAR_HTPC_UPSTREAM` are **mapped from** `DOMAIN` and `HTPC_UPSTREAM` in the Homepage stack environment. Do not duplicate live values in git.

## Notes and bookmarks

| Key | Secret | Used by |
|---|---|---|
| `LINKDING_SUPERUSER_NAME` | | Linkding initial admin (use `admin`) |
| `LINKDING_SUPERUSER_PASSWORD` | secret | Linkding initial admin |

Jotty has no Komodo secret; the first browser visit creates the admin.

## Transcription

Scriberr has no Komodo secret; JWT material is generated in the HTPC data volume. Models stay on local HTPC volumes, not NFS.

## Remote desktop

RustDesk OSS generates its own key pair under `${DATA_ROOT}/system/rustdesk`. No Komodo secret. Do not port-forward 21115–21119; off-LAN is wg-easy.

## Travel

| Key | Secret | Used by |
|---|---|---|
| `ADVENTURELOG_POSTGRES_PASSWORD` | secret | Adventure Log PostGIS |
| `ADVENTURELOG_ADMIN_PASSWORD` | secret | Adventure Log Django admin on first boot |

## Files and photos

| Key | Secret | Used by |
|---|---|---|
| `OPENCLOUD_ADMIN_PASSWORD` | secret | OpenCloud built-in `admin` (`IDM_ADMIN_PASSWORD`) |
| `IMMICH_DB_PASSWORD` | secret | Immich Postgres (`immich` role). Not the Immich UI login |

## NVR

Frigate has no Komodo secret. The first start prints an admin password in `docker logs frigate`. MQTT is anonymous on the HTPC LAN port 1883 (not Caddy). Camera RTSP URLs live in the HTPC `frigate-config` volume, not git.

## File conversion, PDF, translate, read-aloud, workflows, snippets

| Key | Secret | Used by |
|---|---|---|
| `TRANSMUTE_AUTH_SECRET_KEY` | secret | Transmute JWT signing. Must stay fixed across Redeploys |
| `BYTESTASH_JWT_SECRET` | secret | ByteStash |
| `BYTESTASH_ALLOW_NEW_ACCOUNTS` | | ByteStash registration (`true` until the first account, then `false`) |
| `OPENREADER_AUTH_SECRET` | secret | OpenReader session signing. Must stay fixed across Redeploys |
| `N8N_ENCRYPTION_KEY` | secret | n8n credential encryption. Losing it orphans stored credentials |

BentoPDF, IT Tools, and LibreTranslate have no Komodo secret. LibreTranslate models stay on a local HTPC volume, not NFS.

## HTPC apps

| Key | Secret | Used by |
|---|---|---|
| `GRAFANA_ADMIN_PASSWORD` | secret | Grafana |
| `SMB_USERNAME` | | Unused by catalog stacks. SMB is for Explorer/Finder only |
| `SMB_PASSWORD` | secret | Unused by catalog stacks |
