## ADDED Requirements

### Requirement: Single Caddy on the NAS
Caddy SHALL run only on server `nas`. It SHALL bind host ports 80 and 443, terminate `*.{$DOMAIN}` (HTTPS, internal TLS in this catalog), and reverse-proxy to NAS containers on the edge Docker network by name, and to HTPC published ports at `{$HTPC_UPSTREAM}`. No second reverse proxy SHALL be required on the HTPC for these apps. Host nginx (OMV workbench) MUST NOT listen on 80 or 443.

#### Scenario: Hostname is not the OMV workbench
- **WHEN** a LAN client opens `https://dash.{$DOMAIN}` (or another catalogued hostname) with DNS pointing at the NAS
- **THEN** Caddy serves that vhost, not the OMV workbench on port 80

#### Scenario: Jellyfin through Pi Caddy
- **WHEN** a client requests `watch.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to `{$HTPC_UPSTREAM}` on Jellyfin’s published port

#### Scenario: Vaultwarden local
- **WHEN** a client requests `pw.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to the Vaultwarden service on the edge network

### Requirement: Authelia at the edge
Authelia SHALL run on `nas` and SHALL protect Caddy sites via forward auth, except where a stack spec defines a narrower matcher. Vaultwarden SHALL keep Authelia on `/admin` and `/admin/*` only, as specified by the `vaultwarden` capability. Komodo at `ops.{$DOMAIN}` SHALL NOT use Authelia forward auth; Komodo authenticates the UI itself.

#### Scenario: Default app is SSO-gated
- **WHEN** a browser opens Homepage or another Authelia-protected site
- **THEN** Caddy performs Authelia forward auth before the upstream

#### Scenario: Komodo login is not Authelia
- **WHEN** a browser opens `https://ops.{$DOMAIN}`
- **THEN** Caddy proxies to Komodo Core without Authelia forward auth, and Komodo’s own login is used

#### Scenario: Default app is SSO-gated
- **WHEN** a browser opens Homepage or another Authelia-protected site
- **THEN** Caddy performs Authelia forward auth before the upstream

### Requirement: Pi-hole DNS for the domain
Pi-hole SHALL run on `nas` and SHALL answer name resolution for `*.{$DOMAIN}` (and the domain apex as needed) to the NAS LAN IP so clients reach Caddy. The live domain value SHALL come from Komodo, not from git.

#### Scenario: Wildcard to Caddy
- **WHEN** a LAN client resolves `watch.{$DOMAIN}` using Pi-hole
- **THEN** the answer is the NAS address that hosts Caddy

### Requirement: Second Pi-hole on the HTPC
A second Pi-hole SHALL run on `periphery` with DNS published on the HTPC LAN IP. Its config SHALL be a local Docker volume (not NFS) so it can start when Core is down. The `*.{$DOMAIN}` wildcard SHALL still resolve to the NAS LAN IP (Caddy). DHCP MAY list both Pi-holes; it MUST NOT list a public resolver as a third server. Caddy MAY expose the HTPC Pi-hole admin at `dns2.{$DOMAIN}` (this URL is unavailable if Core is down).

#### Scenario: Core DNS is down
- **WHEN** the NAS Pi-hole is unreachable and a client uses the HTPC Pi-hole
- **THEN** the client still receives DNS answers, including `*.{$DOMAIN}` pointing at the NAS address

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
