## ADDED Requirements

### Requirement: Frigate on periphery
Frigate SHALL deploy on `periphery` via ResourceSync using `ghcr.io/blakeblackshear/frigate:stable`. The stack SHALL include an `eclipse-mosquitto` sidecar on the same Compose network. The stack SHALL publish host ports 8971 (authenticated UI/API), 8554 (RTSP restream), 8555/tcp and 8555/udp (WebRTC), and 1883 (MQTT). The stack MUST NOT publish container port 5000. Caddy SHALL proxy `cams.{$DOMAIN}`, `nvr.{$DOMAIN}`, and `frigate.{$DOMAIN}` to `{$HTPC_UPSTREAM}:8971` with long read/write timeouts. Caddy MUST NOT apply Authelia forward-auth to these hostnames. Caddy MUST NOT reverse-proxy MQTT, RTSP, or WebRTC ports. Coral, OpenVINO, CUDA, device passthrough, and `privileged: true` are out of scope.

#### Scenario: UI through Caddy
- **WHEN** a client opens `https://cams.{$DOMAIN}`
- **THEN** Caddy on Core proxies to Frigate’s published 8971 on `HTPC_UPSTREAM`

#### Scenario: Unauthenticated API stays off the host
- **WHEN** Frigate is deployed
- **THEN** host port 5000 is not published

### Requirement: Config local, recordings on shared cameras
Frigate `/config` (including SQLite and the live `config.yml`) SHALL be a local Docker volume on the HTPC. `/media/frigate` SHALL be household data at `shared/cameras`: catalog `compose.yaml` SHALL bind `${DATA_ROOT}/shared/cameras`; catalog `compose.nfs.yaml` SHALL use a Docker NFS volume of `${NFS_EXPORT}/cameras` on `NAS_LAN_IP`. ResourceSync SHALL list exactly one of those files. `/tmp/cache` SHALL be tmpfs. Camera RTSP URLs MUST NOT be stored in git. On first start, if the config volume has no `config.yml` or `config.yaml`, the stack SHALL copy a seed that disables Frigate TLS, points MQTT at the sidecar hostname `mosquitto`, and leaves `cameras` empty.

#### Scenario: Recordings on the NAS tree
- **WHEN** Frigate is deployed with this site’s ResourceSync file
- **THEN** `/media/frigate` is an NFS volume of `/shared/cameras` and `/config` is not NFS

#### Scenario: Seed does not overwrite cameras
- **WHEN** `/config/config.yml` already exists in the volume
- **THEN** a catalog pull does not replace that file

### Requirement: MQTT for Home Assistant
Mosquitto SHALL listen on 1883 with anonymous access for LAN and Docker-network clients. Frigate’s seed MQTT host SHALL be `mosquitto`. Home Assistant SHALL reach the broker at the HTPC published port 1883 (not through Caddy). No Komodo MQTT secret is required.

#### Scenario: HA can reach the broker
- **WHEN** Mosquitto is published on the HTPC
- **THEN** a client on the Docker Desktop host or LAN can connect to `HTPC_UPSTREAM:1883` without Caddy
