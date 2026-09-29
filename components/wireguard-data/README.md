# WireGuard data plane

Rootful host unit: `wg-quick@wg0` (UDP 51820, NAT, MTU 1280). Peer files live in `${site.data.roots.appdata}/wireguard`. The wg-easy UI is a separate rootless component and must not own `wg0`.
