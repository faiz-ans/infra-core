# WireGuard data plane

`wg0` (UDP 51820, NAT, MTU 1280) is created by the root helper `site-wg-helper`. The rootless wg-easy UI asks it to show, bring up, bring down, or sync peers. The helper builds the NAT rules itself. Key generation stays in the UI, and the UI must not own `wg0`. Peer files live in `${site.data.roots.appdata}/wireguard`.
