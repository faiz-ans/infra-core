## ADDED Requirements

### Requirement: Templated services.yaml
Homepage SHALL run on `nas`. Its `services.yaml` (and related Homepage config in the catalog) SHALL live in git and SHALL substitute `{{HOMEPAGE_VAR_…}}` values supplied as container environment from Komodo. Operators MUST NOT hand-copy Homepage YAML onto the host.

#### Scenario: Domain is not committed
- **WHEN** Homepage config is read from git
- **THEN** hrefs use `{{HOMEPAGE_VAR_DOMAIN}}` (and similar) rather than a literal live domain

### Requirement: Public href, internal widget URL
Each catalogued service entry SHALL use a public href through Caddy (`https://<app>.{{HOMEPAGE_VAR_DOMAIN}}` or equivalent). Widget, ping, or siteMonitor URLs SHALL be internal: NAS services on the edge network by container name and port; HTPC services at `http://{{HOMEPAGE_VAR_HTPC_UPSTREAM}}:<port>` using ports defined in the catalog. Widget API keys SHALL be `HOMEPAGE_VAR_*` secrets from Komodo.

#### Scenario: Jellyfin widget bypasses Authelia
- **WHEN** Homepage refreshes the Jellyfin widget
- **THEN** it calls `http://{{HOMEPAGE_VAR_HTPC_UPSTREAM}}:<jellyfin-port>` and does not require Authelia

#### Scenario: Vaultwarden monitor is local
- **WHEN** Homepage monitors Vaultwarden
- **THEN** it uses `http://vaultwarden:80` as specified by the `vaultwarden` capability
