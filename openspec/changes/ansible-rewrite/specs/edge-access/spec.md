## MODIFIED Requirements

### Requirement: Single Caddy on Core
When `networking.ingress` is `caddy` and exactly one workload host lists Caddy, that instance SHALL run rootless in the host network namespace on unprivileged ports (for example 8080/8443). A privileged host redirect SHALL map LAN and tunnel `:80`/`:443` to those ports without hiding client source IPs. Caddy SHALL terminate the site domain and reverse-proxy placed services. Caddy MUST NOT be rootful. OpenMediaVault nginx MUST NOT be present.

#### Scenario: Caddy is rootless and sees the client
- **WHEN** a LAN client opens HTTPS on `:443` after lan-bind
- **THEN** Caddy is a user Quadlet and the connection shows the client source IP

### Requirement: Paired Pi-holes
When desired lists more than one Pi-hole, each SHALL run rootless host-net on an unprivileged DNS port with a host `:53` redirect. Domain names SHALL resolve to the ingress host IP. Each instance’s config SHALL be local (not NFS). DHCP MUST NOT list a public resolver as a third server.

#### Scenario: Second instance still points at ingress
- **WHEN** two Pi-hole instances are placed
- **THEN** both answer `*.<domain>` as the ingress host IP

### Requirement: WireGuard data plane rootful; client UI rootless
When `networking.tunnel.engine` is `wireguard` and placed, the data plane SHALL be rootful and the UI rootless. Factory MTU 1420 SHALL be replaced with 1280 before peers are issued. The client endpoint SHALL be the desired tunnel endpoint hostname.

#### Scenario: Remote client
- **WHEN** a peer is connected to the site WireGuard service
- **THEN** that peer can resolve and use `*.<domain>` through Caddy

### Requirement: Lan-bind only after Pi-hole and Caddy listen
SET SHALL install lan-bind on the ingress host disabled, then enable it only after the official high ports listen. Redirects SHALL include PREROUTING for LAN/tunnel and OUTPUT `:443` to Caddy’s high port for `127.0.0.1` and the host LAN IP so `site` containers can fetch `https://auth.<domain>`. SET MUST NOT OUTPUT-redirect `:53`.

#### Scenario: Enable after listeners
- **WHEN** Pi-hole and Caddy high ports listen
- **THEN** SET enables lan-bind and LAN clients reach `:53`/`:80`/`:443`

#### Scenario: OpenCloud OIDC hairpin
- **WHEN** lan-bind OUTPUT `:443` is active
- **THEN** a `site` container can open `https://auth.<domain>/.well-known/openid-configuration` via pasta loopback, not a refused LAN `:443`

### Requirement: Host DNS must survive the redirect
After lan-bind, the ingress host SHALL still resolve public names. OUTPUT MUST NOT redirect `:53`.

#### Scenario: github.com after lan-bind
- **WHEN** lan-bind is enabled and Pi-hole is up
- **THEN** `getent hosts github.com` on that host succeeds

### Requirement: Authelia at the edge
When Authelia is the SSO engine and placed, Caddy SHALL use generated forward-auth or OIDC per the official pack. Vaultwarden SHALL keep Authelia on `/admin` only when Vaultwarden is placed. Cockpit SHALL not use Authelia forward-auth.

#### Scenario: Default app is SSO-gated
- **WHEN** a browser opens a forward-auth site
- **THEN** Caddy performs Authelia forward-auth before the upstream

## REMOVED Requirements

### Requirement: Single Caddy on the NAS
**Reason**: Docker/`nas`/OMV wording.
**Migration**: “Single Caddy on Core” (ingress host from topology).

### Requirement: Shared edge network
**Reason**: Docker edge network.
**Migration**: Podman `site` network + host-net official exceptions.

### Requirement: Pi-hole DNS for the domain
**Reason**: Superseded by paired Pi-holes + topology placement.
**Migration**: Official pack + desired instances.

### Requirement: Second Pi-hole on the HTPC
**Reason**: HTPC Docker instance; mantle/workload placement replaces it.
**Migration**: Second Pi-hole is a desired workload service.

### Requirement: WireGuard on the NAS
**Reason**: Duplicate of the rootful/rootless requirement with Komodo vars.
**Migration**: WireGuard data plane requirement above.
