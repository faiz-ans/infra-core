# Homepage first-run

Homepage is on the `site` netavark bridge. Caddy, Pi-hole, PeaNUT, Cockpit, and OMV are **host netns**. From `site`, `NAS_LAN_IP` and `127.0.0.1` are connection-refused. Pasta exposes the host loopback as `host.containers.internal` = **`169.254.1.2`**. Catalog tiles that scrape Core host services must use that IPv4 (the name AAAA-stalls Node).

`apply.sh` sets `SITE_HOST_LOOPBACK=169.254.1.2` and `HOMEPAGE_ALLOWED_HOSTS` (includes `dash.<DOMAIN>:8443`). Caddy pins `Host: dash.<DOMAIN>` and disables HTTP/3 (`h1`/`h2` only) so Firefox does not send `Host: dash.<DOMAIN>:8443` via Alt-Svc.

## Container status dots

Homepage talks to the **user** Podman API (Docker-compatible). `apply.sh` starts `podman.socket` for `pilot` and mounts `/run/user/<PUID>/podman` at `/run/podman`. `config/docker.yaml` is `core` → `/run/podman/podman.sock`. Quadlet `UserNS=keep-id` so the socket is readable.

Kube-play names are `{pod}-{container}` (`opencloud-opencloud`). `.container` units use `ContainerName` (`caddy`, `pihole`, `peanut`). Mantle tiles have no `server`/`container` (this socket is Core only). Cockpit, OMV, and the router are host services (no dot). Scrutiny is rootful and is not on this socket.

Click a green dot for Docker-style stats. Undeployed Core-full tiles (Jotty, …) show as down until `core-full`.

## Phase A tiles that must work after lan-bind

| Tile | Scrape URL | Notes |
|---|---|---|
| PeaNUT | `http://169.254.1.2:8092` `key: ups` | Host-net PeaNUT. Details: `peanut.md` |
| Glances (NAS) | `http://glances:61208` | Both on `site` |
| Cockpit | `http://169.254.1.2:9090/ping` | Host `:9090`. `/` 301s to HTTPS and Homepage shows 500 |
| OpenMediaVault | `http://169.254.1.2:81` | Host `:81` |
| Pi-hole | `http://169.254.1.2:<PIHOLE_WEB_PORT>` | Host-net; default `8088`. `key` = `PIHOLE_WEBPASSWORD` (v6). `apply.sh` maps it; not a second site.env token |
| Caddy admin | `http://169.254.1.2:2019` | Origins include `169.254.1.2:2019` |

Browser: `https://dash.<DOMAIN>` (alias `homepage.`). No Authelia gate.

Glances on mantle (`SURFACE_UPSTREAM:61208`) and router `siteMonitor` are **other hosts** — LAN works. Do not point those at `169.254.1.2`.

## Do not

- Widget/siteMonitor `http://<NAS_LAN_IP>:…` or `http://127.0.0.1:…` (Homepage’s own loopback / hairpin)
- Widget `http://peanut`, `http://pihole`, `http://caddy` (those names are host-net, not `site` DNS)
- Widget `http://host.containers.internal:8092` (works, AAAA stall)
- Extra `Network=slirp4netns` / `pasta` on a `site` unit (this Podman: invalid network mode)
- Restore a laptop Homepage YAML that still has LAN scrape URLs

## If it fails

| Symptom | Cause / fix |
|---|---|
| Firefox laptop 400 / “invalid host”, phone works | `HOMEPAGE_ALLOWED_HOSTS` missing `:8443`, or Caddy still advertises HTTP/3. re-apply **homepage** + **caddy**. Clear site data for `dash.<DOMAIN>` |
| Firefox NXDOMAIN `dash.<DOMAIN>`, `dig` works | macOS mDNSResponder negative cache (~30h). Flush or use `dash.<DOMAIN>:8443` once, or wait |
| PeaNUT / Caddy / Cockpit / OMV tile API error | Scrape URL must be `http://169.254.1.2:<port>`. From Homepage: `wget -qO- --timeout=5 http://169.254.1.2:8092/api/ping` → `pong` |
| Pi-hole tile API error, `wget` to `:8088/api/auth` is **401** | Reachability is fine (unauthenticated GET is 401). Widget key must be `PIHOLE_WEBPASSWORD`. `apply.sh` maps it onto `HOMEPAGE_VAR_PIHOLE_TOKEN`. Do not keep a leftover v5 API token in site.env. re-apply **homepage** |
| Core Glances tile empty | `wget` from Homepage to `http://glances:61208/api/4/cpu`. re-apply **glances** (apply retries once; kube-play can flap) |
| Click opens `http://glances:61208` | Stale href. re-apply **homepage** |
| No status dots / all tiles gray | User `podman.socket` down or socket not mounted. `systemctl --user is-active podman.socket`; `ls /run/user/$(id -u)/podman/podman.sock`. re-apply **homepage** |
| Dots missing only on mantle tiles | Expected. Core Homepage cannot see mantle Podman. |
| Cockpit tile 500, login page still opens | `siteMonitor` must be `http://169.254.1.2:9090/ping` (not `/`). `/` 301s to Cockpit TLS. re-apply **homepage** |
| `box.<DOMAIN>` login as `pilot` fails / blank after submit | No `/etc/cockpit/cockpit.conf`. `apply.sh` writes Origins for `box.`/`cockpit.` and Caddy proxies `https://127.0.0.1:9090`. re-apply **caddy**. Then `https://box.<DOMAIN>` again |
