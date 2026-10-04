# WireGuard: rootless UI, and internet through the tunnel

Working state when `wireguard` is listed on a workload host in `site.yaml`. SET installs it. Do not SSH a fix onto the host.

## Clients page spins, creating a client returns a server error

The UI is a rootless host-netns Quadlet. Its root is the workload user on the host, so `wg show` returns `Operation not permitted` and `wg0` is never created. `wireguard-tools` may also be absent until SET installs it.

The UI stays rootless. A root helper (`components/wg-easy/site-wg-helper`, unit `site-wg-helper.service`) accepts only `show`, `up`, `down`, and `sync`. It builds `wg0` and the NAT rules. It does not run UI iptables text or config hooks (`PostUp` is bash `eval` in `wg-quick`). `genkey`, `pubkey`, `genpsk`, and `wg-quick strip` stay in the container via `/usr/bin/wg` and `/usr/bin/wg-quick`. The wrappers in `components/wg-easy/handoff/` only translate the four operations. The socket is `${appdata}/wireguard/.wg-helper.sock`, bind-mounted at `/etc/wireguard/.wg-helper.sock`, mode `0666`, and the helper allows the workload uid (the container's root maps to that uid).

`handoff/bin/*` are symlinks to `../handoff.sh`, which lives next to `handoff.mjs`, not inside `bin/`. A broken link makes `install_quadlets.py` `copytree` fail with `No such file or directory` on those names.

## LAN sites work, public internet does not

Site names work because they resolve to this host and are delivered locally. Internet is forwarded. Check these before changing the helper:

1. `wg show` has a recent handshake.
2. On `wg0`, packets from `10.8.0.0/24` to a public `:443` (TCP or UDP).
3. `iptables -t nat -L POSTROUTING -n -v` for `MASQUERADE -s 10.8.0.0/24 -o <uplink>`. If public packets are on `wg0` and this counter does not move, the packets are captured before they are forwarded.

That capture is lan-bind. `PREROUTING` was redirecting every `:53`, `:80`, and `:443` to Pi-hole and Caddy, with no destination match. A peer packet to Google `:443` was redirected onto this host. Caddy has no such vhost. The masquerade rule never saw it.

The redirects now use `-m addrtype --dst-type LOCAL` (`ansible/roles/lan_bind/files/lan-bind`). Only an address of this host is redirected. Placing or changing `wireguard` re-applies lan-bind (`ansible/lib/diff.py`) so an older unrestricted rule cannot remain.

A ping from the host sourced at `10.8.0.1` to `1.1.1.1` proves the uplink and the masquerade rule. It does not prove that peer packets are forwarded.

## Checked, and not the internet failure

These were already true on the host while internet was still broken. Do not start here if the masquerade counter is flat.

- `net.ipv4.ip_forward=1`, `FORWARD` policy `ACCEPT`, and `FORWARD -i/-o wg0 ACCEPT`. The Docker-era script `archive/bootstrap/core/core-lan-bind` inserted those accepts at the front of `FORWARD` and set `wg0` `rp_filter=2`. The helper still does both on `up`. They were not what stole `:443`.
- Client profiles at MTU 1420 while `wg0` is 1280. `wg0` can show transmit errors for oversized packets. The seed must rewrite factory `1420` on the interface, `clients_table`, and `user_configs_table.default_mtu` (`components/wg-easy/seed-mtu.mjs`). The helper also clamps forwarded TCP MSS to the tunnel MTU minus 40. Replacing the phone profile picks up 1280. That did not make internet work while lan-bind was still redirecting every `:443`.

## What SET installs

- Rootless `wg-easy`, host netns, no `CAP_NET_ADMIN`. Helper, `wireguard-tools`, and `net.ipv4.ip_forward=1` from the quadlets role.
- On `up`: masquerade `-s <tunnel> -o <dev from ip route get 1.1.1.1>`, `FORWARD` accepts inserted at position 1, loose `rp_filter` on `wg0`, TCP MSS clamp.
- lan-bind redirects limited to local destinations.
- Client DNS is the ingress host IP. Client MTU 1280.
