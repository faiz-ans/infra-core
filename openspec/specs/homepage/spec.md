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

### Requirement: Podman status dots via docker-proxy
Homepage SHALL show container status for every workload user's Podman API: Core `pilot`, Core `hostess`, and Mantle `pilot`. Each of those users SHALL run `docker-proxy` (tecnativa/docker-socket-proxy) with `POST=0` and only container read endpoints enabled. Homepage SHALL reach those proxies over HTTP from `docker.yaml`. It MUST NOT mount a Podman socket. A read-only socket mount does not block API writes. It MUST NOT use Komodo API keys. Host stats SHALL use Glances. Container restart/inspect SHALL remain Cockpit.

The proxy's host port is `2375` plus that user's index among the host's workload users (`pilot` is `2375`, `hostess` is `2376` on Core).

#### Scenario: Status dots from each workload
- **WHEN** Homepage is applied and each workload user's `docker-proxy` is up
- **THEN** tiles use `core-pilot`, `core-hostess`, or `mantle-pilot`, and Homepage has no Podman socket mount
