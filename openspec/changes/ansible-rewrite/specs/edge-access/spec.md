## MODIFIED Requirements

### Requirement: Single Caddy on Core
When `networking.ingress` is `caddy` and exactly one workload host lists Caddy, that instance SHALL run rootless in the host network namespace on unprivileged ports (for example 8080/8443). A privileged host redirect SHALL map `:80`/`:443` to those ports only when the destination is an address of this host, without hiding client source IPs. Packets forwarded to any other destination MUST NOT be redirected. Caddy SHALL terminate the site domain and reverse-proxy placed services. Caddy MUST NOT be rootful. OpenMediaVault nginx MUST NOT be present.

#### Scenario: Caddy is rootless and sees the client
- **WHEN** a LAN client opens HTTPS on `:443` after lan-bind
- **THEN** Caddy is a user Quadlet and the connection shows the client source IP

### Requirement: Paired Pi-holes
When desired lists more than one Pi-hole, each SHALL run rootless host-net on an unprivileged DNS port with a host `:53` redirect. Domain names SHALL resolve to the ingress host IP. Each instance’s config SHALL be local (not NFS). DHCP MUST NOT list a public resolver as a third server.

#### Scenario: Second instance still points at ingress
- **WHEN** two Pi-hole instances are placed
- **THEN** both answer `*.<domain>` as the ingress host IP

### Requirement: WireGuard data plane rootful; client UI rootless
When `networking.tunnel.engine` is `wireguard` and placed, the data plane SHALL be a root helper that accepts structured `show`, `up`, `down`, and `sync` operations. It SHALL build `wg0` and its NAT rules itself and MUST NOT execute UI-supplied iptables text or config hooks. Key generation SHALL stay in the UI. The wg-easy UI SHALL stay rootless in the host network namespace. SET SHALL persist `net.ipv4.ip_forward=1` on that host. Factory MTU 1420 SHALL be replaced with 1280 on the interface, the client default, and existing factory clients before peers are issued. A peer's packets to a destination that is not this host SHALL be forwarded and NATed. Placing WireGuard SHALL re-apply the host port redirects. The client endpoint SHALL be the desired tunnel endpoint hostname.

#### Scenario: Remote client
- **WHEN** a peer is connected to the site WireGuard service
- **THEN** that peer can resolve and use `*.<domain>` through Caddy

#### Scenario: Clients page can read the interface
- **WHEN** an operator opens the clients page
- **THEN** the rootless UI hands `wg show` to the root helper, which reads the host `wg0`

### Requirement: Lan-bind only after Pi-hole and Caddy listen
SET SHALL install lan-bind on the ingress host disabled, then enable it only after the official high ports listen. PREROUTING redirects SHALL match only a destination address of this host, for clients on the LAN or on the tunnel. OUTPUT `:443` SHALL redirect `127.0.0.1` and the host LAN IP to Caddy’s high port so `site` containers can fetch `https://auth.<domain>`. SET MUST NOT OUTPUT-redirect `:53`.

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
