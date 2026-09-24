## ADDED Requirements

### Requirement: Single Caddy on Core
Caddy SHALL run only on `core` as a **rootless** Quadlet in the host network namespace. It SHALL listen on unprivileged TCP/UDP ports (catalog high ports, e.g. 8080/8443). A privileged **host** nft/iptables unit SHALL REDIRECT (or equivalent source-preserving DNAT that remains in the host netns) LAN and WireGuard `:80` and `:443` (TCP and UDP) to those ports. Caddy MUST bind those high ports on all host interfaces so both the LAN address and `wg0` are served. It SHALL terminate `*.{$DOMAIN}` (HTTPS, internal TLS in this catalog) and reverse-proxy to Core apps by Podman DNS/name or localhost, and to mantle published ports at `{$SURFACE_UPSTREAM}`. No second reverse proxy SHALL be required on `surface`. Host nginx (OMV workbench) MUST NOT listen on 80 or 443. Caddy MUST NOT be a rootful container. The redirect MUST NOT target `127.0.0.1` plus a userspace proxy in a way that replaces the client source address.

#### Scenario: Jellyfin through Pi Caddy
- **WHEN** a client requests `watch.{$DOMAIN}`
- **THEN** Caddy on Core proxies to `{$SURFACE_UPSTREAM}` on Jellyfin’s published port

#### Scenario: Caddy is rootless and sees the client
- **WHEN** a LAN or WireGuard client opens HTTPS on `:443`
- **THEN** the Caddy process is a user Quadlet and its connection log (or equivalent) shows that client’s source IP, not `127.0.0.1` or a slirp/pasta gateway alone

### Requirement: Authelia at the edge
Authelia SHALL run on `core` and SHALL protect Caddy sites via forward auth, except where a component spec defines a narrower matcher. Vaultwarden SHALL keep Authelia on `/admin` and `/admin/*` only. Cockpit SHALL authenticate itself and MUST NOT use Authelia forward auth unless later opted in. There SHALL be no Komodo `ops` vhost.

#### Scenario: Default app is SSO-gated
- **WHEN** a browser opens Homepage or another Authelia-protected site
- **THEN** Caddy performs Authelia forward auth before the upstream

### Requirement: Paired Pi-holes
Pi-hole SHALL run **rootless** in the host network namespace on `core` and on `mantle`. Each instance SHALL listen on an unprivileged port (e.g. 15353) on all interfaces. A privileged host redirect SHALL map that host’s DNS address `:53` to that port (Core: extend `core-lan-bind`; do not DNAT solely to `127.0.0.1` then proxy). `*.{$DOMAIN}` SHALL still resolve to the NAS LAN IP (Caddy). Mantle Pi-hole config SHALL be a local volume (not NFS). DHCP MAY list both Pi-holes; it MUST NOT list a public resolver as a third server. FTL SHALL see the real client source IP for LAN and WireGuard queries.

#### Scenario: Core DNS is down
- **WHEN** the NAS Pi-hole is unreachable and a client uses the mantle Pi-hole
- **THEN** the client still receives DNS answers, including `*.{$DOMAIN}` pointing at the NAS address

#### Scenario: Pi-hole query log shows the client
- **WHEN** a LAN host queries Core Pi-hole via `:53`
- **THEN** the query is answered and the logged client address is that host, not only loopback or a container bridge

### Requirement: WireGuard data plane rootful; client UI rootless
The WireGuard **data plane** (`wg0`, routing/NAT, UDP 51820) SHALL run as privileged host plumbing on `core` (`wg-quick` or equivalent). It MUST NOT run as a rootless tun container. Remote peers SHALL reach `*.{$DOMAIN}` as if on LAN. Client DNS SHALL be `NAS_LAN_IP`. Catalog seed and/or first-run SHALL keep client MTU 1280. The WireGuard **client/peer UI** (wg-easy, port 51821) SHALL run as a **rootless** host-netns Quadlet. Caddy SHALL reverse-proxy the VPN UI to that port, not via a Docker `host.docker.internal` name. Site values SHALL stay in attributes, not plaintext git. Netbird SHALL NOT replace this VPN.

#### Scenario: Remote client
- **WHEN** a peer is connected to the NAS WireGuard service
- **THEN** that peer can resolve and use `*.{$DOMAIN}` through Caddy

#### Scenario: UI is not the data plane
- **WHEN** an operator opens the catalogued VPN hostname
- **THEN** Caddy reaches the rootless wg-easy UI while `wg0` is still a host/rootful interface

### Requirement: RustDesk rootless host network
RustDesk OSS `hbbs` and `hbbr` SHALL run **rootless** with host networking on `core` so UDP 21116 sees real peer IPs. They SHALL NOT use an nft/iptables port redirect and MUST NOT be DNAT’d to loopback. The catalog MUST NOT publish 21115–21119 through Caddy or the site router; off-LAN desktop remains WireGuard first.

#### Scenario: LAN peer IP
- **WHEN** a LAN RustDesk client registers with hbbs
- **THEN** the ID server sees that client’s LAN (or WG) source address, not a bridge or `127.0.0.1`

### Requirement: Core app mesh without Docker edge network
Core apps that Caddy and Homepage must reach by name SHALL share a Podman network (or equivalent kube-play pod grouping) created as a Quadlet `.network`. WireGuard SHALL NOT be on that network. `host.docker.internal` MUST NOT be required; host access SHALL use `host.containers.internal` or host ports.

#### Scenario: Homepage reaches Vaultwarden by name
- **WHEN** Homepage scrapes Vaultwarden on the Core app network
- **THEN** that name resolves without using `SURFACE_UPSTREAM`
