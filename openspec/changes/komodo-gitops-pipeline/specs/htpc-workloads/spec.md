## ADDED Requirements

### Requirement: Media and download stacks on htpc
Jellyfin, the Arr stack, and qBittorrent SHALL deploy on server `htpc` via ResourceSync. They SHALL mount `${DATA_ROOT}/shared/media` and `${DATA_ROOT}/shared/downloads` (and shall not use the laptop internal SSD as the media library). They SHALL be reachable from Caddy on `nas` via `HTPC_UPSTREAM` and their published ports.

#### Scenario: Jellyfin library on NAS
- **WHEN** Jellyfin is deployed
- **THEN** its library path is `${DATA_ROOT}/shared/media` as seen by Docker Desktop

### Requirement: Nextcloud on htpc
Nextcloud SHALL deploy on `htpc` and SHALL access both household and per-user trees: `${DATA_ROOT}/shared/files`, `${DATA_ROOT}/shared/photos`, `${DATA_ROOT}/users/<user>/files`, and `${DATA_ROOT}/users/<user>/photos`.

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
