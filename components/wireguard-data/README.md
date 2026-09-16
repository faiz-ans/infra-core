# WireGuard data plane (`core`)

Rootful host unit: `wg-quick@wg0` (UDP 51820, NAT). Peer files live in `${DATA_ROOT}/system/wireguard`. The wg-easy UI is a separate rootless component and must not own `wg0`.

Bootstrap installs/enables `wg-quick@wg0`. Materia only ensures the static unit is started.
