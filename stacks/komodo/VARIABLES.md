## Site secrets (topology-driven)

`bootstrap/core.sh` and `bootstrap/sync-komodo-secrets.sh` write Komodo `[secrets]` from **enabled topology stacks** (and always-on Caddy / Authelia / Pi-hole / OpenCloud). Keys for stacks with `deploy = false` in their fragment are skipped until you enable Deploy and re-run sync.

After adding a stack to `topology.inc` and regenerating TOML:

```bash
sudo bash bootstrap/sync-komodo-secrets.sh
# recreate Komodo Core so it reloads [secrets]
```

Do not create those variables by hand in the Komodo UI.

Mark items tagged **secret** as secrets in Komodo when inspecting the file.

## Site

| Key | Secret | Used by |
|---|---|---|
| `CATALOG_REPO` | | Informational. Catalog git path is `faiz-ans/infra-core`. Stacks clone GitHub; ResourceSync Selects the Komodo Repo named `infra-core`. After Gitea is origin, set that Repo’s git provider to `gitea:3000` (see `bootstrap/gitea.md`). |
| `CORE_SERVER` | | Bootstrap `connect_as` / first server. Must match TOML `server = "core"` and the Core OS hostname (Pi-hole `host-record` for SSH/SMB short name). |
| `PERIPHERY_SERVER` | | Remote Periphery `connect_as`. Must match TOML `server = "periphery"` |
| `DOMAIN` | | Caddy, Authelia, Pi-hole, Homepage, Vaultwarden public URL |
| `TZ` | | Most containers |
| `NAS_LAN_IP` | | Pi-hole wildcard (`*.DOMAIN` → Caddy), Homepage/Prometheus scrape, periphery NFS `addr=`. Bootstrap pins this as a static address on the Core uplink (`core-lan-static.sh`); do not rely on a DHCP reservation for the host. |
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
| `AUTHELIA_JWT_SECRET` | secret | Authelia (unused by current config; kept for older stacks) |
| `AUTHELIA_SESSION_SECRET` | secret | Authelia |
| `AUTHELIA_STORAGE_ENCRYPTION_KEY` | secret | Authelia |
| `AUTHELIA_OIDC_HMAC_SECRET` | secret | Authelia OIDC HMAC |
| `OIDC_CLIENT_SECRET` | secret | Shared confidential OIDC client secret (Grafana, Gitea, Komodo, Immich, Linkding, Jotty, Transmute, ByteStash, Adventure Log). Authelia stores the hash on disk, not this value. |
| `WG_HOST` | | wg-easy INIT_HOST. Public DNS name that resolves off-LAN to the WAN IPv4 (Dynamic DNS if the WAN moves). Not a LAN-only name. |
| `WG_UI_PASSWORD` | secret | wg-easy v15 admin password (plaintext; used only at first start) |
| `PIHOLE_WEBPASSWORD` | secret | Core Pi-hole web/API password (`FTLCONF_webserver_api_password`). Empty disables the login page. |
| `PIHOLE_PERIPHERY_WEBPASSWORD` | secret | HTPC Pi-hole web/API password. Empty disables the login page. |

Authelia user hashes live in `${DATA_ROOT}/system/authelia/users.yml` on the NAS (written by bootstrap / `bootstrap/authelia-oidc.sh`), not in Komodo. Users are `faiz` (groups `admins` + `users`) and `diana` (group `users`). OIDC JWKS and the client-secret digest are `${DATA_ROOT}/system/authelia/oidc.pem` and `client_secret_digest`. See `bootstrap/authelia.md`.

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
| `WEATHER_LATITUDE` | |
| `WEATHER_LONGITUDE` | |

`HOMEPAGE_VAR_WGEASY_PASSWORD` is the live wg-easy `wg-admin` login (not `WG_UI_PASSWORD` unless you never changed it). wg-easy 2FA must stay off for the widget API.

`WEATHER_LATITUDE` and `WEATHER_LONGITUDE` are decimal degrees for the Homepage Open-Meteo widget (home location, not each browser). West of Greenwich is negative. Names must be exactly those two keys (not `HOMEPAGE_VAR_WEATHER_*`). After creating them, Redeploy **homepage** so Komodo rewrites `.env` and recreates the container. Empty values fall back to browser geolocation. Units are imperial. Timezone is mapped from `TZ`.

`HOMEPAGE_VAR_DOMAIN` and `HOMEPAGE_VAR_HTPC_UPSTREAM` are **mapped from** `DOMAIN` and `HTPC_UPSTREAM` in the Homepage stack environment. `HOMEPAGE_VAR_PIHOLE_TOKEN` is **mapped from** `PIHOLE_WEBPASSWORD` (Pi-hole v6 web/API password, or an app password from Pi-hole Settings → API if the widget shows API Error). Do not duplicate live values in git. Homepage only substitutes `{{HOMEPAGE_VAR_*}}` in YAML (not `${{PIHOLE_WEBPASSWORD}}`).

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
