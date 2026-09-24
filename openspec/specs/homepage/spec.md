## Purpose

TBD

## Requirements

### Requirement: Templated services.yaml
Homepage SHALL run on `core`. Its `services.yaml` (and related Homepage config) SHALL live in the catalog component and SHALL substitute `{{HOMEPAGE_VAR_…}}` values from container environment supplied by Materia attributes. Operators MUST NOT hand-copy Homepage YAML onto the host. This site’s customized `config/` SHALL be migrated into the component, not replaced by seed blindly.

#### Scenario: Domain is not committed
- **WHEN** Homepage config is read from git
- **THEN** hrefs use `{{HOMEPAGE_VAR_DOMAIN}}` (and similar) rather than a literal live domain

### Requirement: Public href, internal widget URL
Each catalogued service entry SHALL use a public href through Caddy. Widget, ping, or siteMonitor URLs SHALL be internal: Core services on the app network by name and port; mantle services at `http://{{HOMEPAGE_VAR_SURFACE_UPSTREAM}}:<port>`. Widget API keys SHALL be `HOMEPAGE_VAR_*` from attributes.

#### Scenario: Jellyfin widget bypasses Authelia
- **WHEN** Homepage refreshes the Jellyfin widget
- **THEN** it calls `http://{{HOMEPAGE_VAR_SURFACE_UPSTREAM}}:<jellyfin-port>` and does not require Authelia

### Requirement: Podman status dots, no Komodo
Homepage SHALL mount the **user** Podman API socket (`/run/user/<PUID>/podman`) and use `docker.yaml` so Core tiles show the same running/stopped dots as the old Docker integration. It MUST NOT use the rootful `/run/podman/podman.sock` or Komodo API keys. Host stats SHALL use Glances. Container restart/inspect SHALL remain Cockpit.

#### Scenario: Core container dots
- **WHEN** Homepage is applied and user `podman.socket` is up
- **THEN** Phase A Core tiles (OpenCloud, Authelia, Caddy, Pi-hole, PeaNUT) show status dots, and `HOMEPAGE_VAR_KOMODO_*` is not required
