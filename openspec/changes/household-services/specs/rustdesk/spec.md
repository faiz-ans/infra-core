## ADDED Requirements

### Requirement: RustDesk ID and relay on Core host network
RustDesk OSS `hbbs` and `hbbr` SHALL deploy on server `core` with host networking. They SHALL share `${DATA_ROOT}/system/rustdesk` so both read the same key pair. `hbbs` SHALL advertise relay `${NAS_LAN_IP}:21117`. The stack MUST NOT attach to the `edge` Docker network. The catalog MUST NOT publish 21115–21119 through Caddy as TCP/UDP streams or HTTP reverse proxies of the native protocol.

#### Scenario: Relay address is the NAS LAN IP
- **WHEN** hbbs starts
- **THEN** clients are told to use `${NAS_LAN_IP}:21117` as the relay, not a Docker bridge address

### Requirement: No public RustDesk ports
The catalog and first-run documentation MUST NOT instruct operators to port-forward TCP/UDP 21115–21119 on the site router. Off-LAN remote desktop SHALL require an existing wg-easy session (client DNS already `NAS_LAN_IP`). LAN and WireGuard clients SHALL reach ID/relay at `desk.{$DOMAIN}` (Pi-hole wildcard to `NAS_LAN_IP`) or at `NAS_LAN_IP` directly.

#### Scenario: Off-LAN without WireGuard
- **WHEN** a client on the public internet tries to reach the RustDesk ID server without a WireGuard tunnel and the router does not forward 21115–21119
- **THEN** the connection fails

#### Scenario: Off-LAN with WireGuard
- **WHEN** a peer is connected to wg-easy and the RustDesk client uses `desk.{$DOMAIN}` or `NAS_LAN_IP` as ID and relay
- **THEN** that client can register with hbbs using the catalogued public key

### Requirement: Optional HTTPS hint page only
Caddy MAY serve `desk.{$DOMAIN}` and `rustdesk.{$DOMAIN}` as an internal-TLS static response that tells operators to use the native client. That vhost MUST NOT terminate or forward the RustDesk rendezvous or relay protocol.

#### Scenario: Homepage href is not a desktop session
- **WHEN** a browser opens `https://desk.{$DOMAIN}`
- **THEN** Caddy returns a short explanation and does not proxy to hbbs or hbbr
