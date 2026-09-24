## ADDED Requirements

### Requirement: Media and download stacks on htpc
Jellyfin, the Arr stack, and qBittorrent SHALL deploy on server `htpc` via ResourceSync. They SHALL mount the OMV `shared/media` and `shared/downloads` trees over NFS (and shall not use the laptop internal SSD as the media library). They SHALL be reachable from Caddy on `nas` via `HTPC_UPSTREAM` and their published ports. The Arr stack SHALL include FlareSolverr on the same Compose network as Prowlarr. FlareSolverr MUST NOT be published on the host or proxied by Caddy.

#### Scenario: Jellyfin library on NAS
- **WHEN** Jellyfin is deployed
- **THEN** its library path is the OMV `shared/media` tree mounted over NFS

#### Scenario: Prowlarr can reach FlareSolverr
- **WHEN** the Arr stack is deployed
- **THEN** Prowlarr can use `http://flaresolverr:8191` on the stack network and FlareSolverr is not published on the HTPC LAN

### Requirement: Seerr on htpc
Seerr SHALL deploy on `htpc` with a local Docker volume for `/app/config`. It SHALL be proxied by Caddy on `nas`. It MUST NOT mount `shared/media`.

#### Scenario: Requests through Caddy
- **WHEN** a client opens the Seerr public hostname on `{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to Seerr’s published port on `HTPC_UPSTREAM`

### Requirement: Nextcloud on htpc
Nextcloud SHALL deploy on `htpc` and SHALL access both household and per-user trees over NFS: `shared/files`, `shared/photos`, and `users/<user>/{files,photos}`.

#### Scenario: Memories and household files
- **WHEN** Nextcloud is deployed
- **THEN** it can mount or otherwise use `shared/{files,photos}` and `users/<user>/{files,photos}`

### Requirement: Home Assistant on htpc
Home Assistant SHALL deploy on `htpc` for wifi and integrations only. USB radio passthrough is out of scope. It SHALL be proxied by Caddy on `nas`.

#### Scenario: HA through Caddy
- **WHEN** a client opens the Home Assistant public hostname on `{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to HA’s published port on `HTPC_UPSTREAM`

### Requirement: Monitoring on htpc
Prometheus and Grafana SHALL deploy on `htpc`. Grafana SHALL be proxied by Caddy on `nas`. Scrape targets MAY include NAS endpoints via addresses supplied as Komodo variables, not as literals in git.

#### Scenario: Grafana is catalogued
- **WHEN** ResourceSync applies HTPC stacks
- **THEN** Prometheus and Grafana are running on `htpc`
