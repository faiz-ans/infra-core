## ADDED Requirements

### Requirement: Jotty on Core with edge proxy
Jotty SHALL deploy on server `core`, attach to the `edge` Docker network, and SHALL NOT publish a host port. Caddy SHALL proxy `notes.{$DOMAIN}` and `jotty.{$DOMAIN}` to the Jotty service by container name on port 3000. Persistent data, config, and cache SHALL live under `${DATA_ROOT}/system/jotty`. The container MUST run as `${PUID}:${PGID}`. `APP_URL` SHALL be `https://notes.${DOMAIN}`. Caddy MUST NOT apply Authelia forward-auth to these hostnames.

#### Scenario: Notes through Caddy
- **WHEN** a client opens `https://notes.{$DOMAIN}`
- **THEN** Caddy on Core proxies to Jotty on the edge network and does not proxy to an HTPC published port

#### Scenario: State on DATA_ROOT
- **WHEN** Jotty is deployed
- **THEN** notes and checklists persist under `${DATA_ROOT}/system/jotty` and are included in a NAS restic snapshot of `DATA_ROOT`
