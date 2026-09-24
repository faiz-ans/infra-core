## ADDED Requirements

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

### Requirement: No Docker or Komodo widgets
Homepage MUST NOT mount `docker.sock` or a Docker socket-proxy. Homepage MUST NOT require Komodo API keys. Host stats SHALL use Glances (or equivalent HTTP APIs). Container restart/inspect SHALL be Cockpit, not Homepage Docker status dots.

#### Scenario: docker.yaml is gone
- **WHEN** Homepage is applied from the new catalog
- **THEN** it has no Docker provider config and no `HOMEPAGE_VAR_KOMODO_*` requirement
