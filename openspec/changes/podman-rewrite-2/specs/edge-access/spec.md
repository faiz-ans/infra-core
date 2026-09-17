## ADDED Requirements

### Requirement: Lan-bind only after Pi-hole and Caddy listen
A privileged host unit MAY REDIRECT LAN and WireGuard `:53` to Pi-hole’s high port and `:80`/`:443` (TCP and UDP) to Caddy’s high ports, preserving source addresses in the host netns. Bootstrap MUST install that unit disabled. The operator SHALL enable it only after `:15353`, `:8080`, and `:8443` already listen. Caddy and Pi-hole SHALL bind those high ports on all host interfaces. The redirect MUST NOT target `127.0.0.1` plus a userspace proxy in a way that replaces the client source address.

#### Scenario: Layer 0 does not black-hole DNS
- **WHEN** `core.sh` has finished and Pi-hole is not yet running
- **THEN** host REDIRECT of `:53` is not active and the host can resolve a public name via public DNS

#### Scenario: Enable after listeners
- **WHEN** Pi-hole is listening on `:15353` and Caddy on `:8080` and `:8443`
- **THEN** the operator can enable `core-lan-bind` and LAN clients reach DNS/HTTP/HTTPS on `:53`/`:80`/`:443`

### Requirement: Host DNS must survive the redirect
After lan-bind is enabled, Core SHALL still resolve public names. systemd-resolved (or equivalent) MAY use `127.0.0.1:15353` with FallbackDNS that is not swallowed by the OUTPUT REDIRECT, or the redirect MUST exclude host-to-self so FallbackDNS works.

#### Scenario: github.com after lan-bind
- **WHEN** lan-bind is enabled and Pi-hole is up
- **THEN** `getent hosts github.com` on Core succeeds
