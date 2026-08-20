## ADDED Requirements

### Requirement: Single Caddy on the NAS
Caddy SHALL run only on server `nas`. It SHALL bind host ports 80 and 443, terminate `*.{$DOMAIN}` (HTTPS, internal TLS in this catalog), and reverse-proxy to NAS containers on the edge Docker network by name, and to HTPC published ports at `{$HTPC_UPSTREAM}`. No second reverse proxy SHALL be required on the HTPC for these apps. Host nginx (OMV workbench) MUST NOT listen on 80 or 443.

#### Scenario: Hostname is not the OMV workbench
- **WHEN** a LAN client opens `https://dash.{$DOMAIN}` (or another catalogued hostname) with DNS pointing at the NAS
- **THEN** Caddy serves that vhost, not the OMV workbench on port 80

#### Scenario: Jellyfin through Pi Caddy
- **WHEN** a client requests `jellyfin.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to `{$HTPC_UPSTREAM}` on Jellyfin’s published port

#### Scenario: Vaultwarden local
- **WHEN** a client requests `pw.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to the Vaultwarden service on the edge network

### Requirement: Authelia at the edge
Authelia SHALL run on `nas` and SHALL protect Caddy sites via forward auth, except where a stack spec defines a narrower matcher. Vaultwarden SHALL keep Authelia on `/admin` and `/admin/*` only, as specified by the `vaultwarden` capability.

#### Scenario: Default app is SSO-gated
- **WHEN** a browser opens Homepage or another Authelia-protected site
- **THEN** Caddy performs Authelia forward auth before the upstream

### Requirement: Pi-hole DNS for the domain
Pi-hole SHALL run on `nas` and SHALL answer name resolution for `*.{$DOMAIN}` (and the domain apex as needed) to the NAS LAN IP so clients reach Caddy. The live domain value SHALL come from Komodo, not from git.

#### Scenario: Wildcard to Caddy
- **WHEN** a LAN client resolves `jellyfin.{$DOMAIN}` using Pi-hole
- **THEN** the answer is the NAS address that hosts Caddy

### Requirement: WireGuard on the NAS
WireGuard SHALL run on `nas` so remote clients can reach `*.{$DOMAIN}` as if on LAN. Endpoint and keys SHALL be Komodo secrets.

#### Scenario: Remote client
- **WHEN** a peer is connected to the NAS WireGuard service
- **THEN** that peer can resolve and use `*.{$DOMAIN}` through Caddy

### Requirement: Shared edge network
Caddy, Authelia, Homepage, Pi-hole, WireGuard, and Vaultwarden SHALL attach to a shared external Docker network on `nas` so they can reach each other by Compose service or container name.

#### Scenario: Homepage reaches Vaultwarden by name
- **WHEN** Homepage scrapes `http://vaultwarden:80`
- **THEN** DNS on the edge network resolves that name without using `HTPC_UPSTREAM`
