## Context

The catalog already splits always-on Core apps (edge network + Caddy by container name) from HTPC apps (published ports + `{$HTPC_UPSTREAM}`). WireGuard is host-network on Core; the only router forward is UDP 51820. Core is a 4GB NAS. This change adds five household apps without waiting on the IronWolf `DATA_ROOT` move.

## Goals / Non-Goals

**Goals:**

- Notes, bookmarks, remote desktop rendezvous, cameras, and a travel log are catalogued GitOps stacks.
- Off-LAN use of every new app (including RustDesk) requires wg-easy, same as existing `*.{$DOMAIN}` services.
- RustDesk ID/relay MUST NOT be published on the WAN. No Caddy TCP/UDP stream for 21115–21119. No router forwards for those ports.
- New Core state lives under `${DATA_ROOT}/system/<app>`. ZoneMinder recordings live under `shared/cameras` (NFS), not `system/`.
- Site values stay in Komodo.

**Non-Goals:**

- Authelia OIDC / proxy auth for these apps.
- RustDesk Server Pro (web console on 21114).
- Migrating `DATA_ROOT` onto the IronWolf.
- ZoneMinder object-detection / MLAPI / GPU.
- Frigate or any NVR other than ZoneMinder.
- Opening WireGuard or Caddy 80/443 policy beyond what already exists.

## Decisions

### 1. Placement: small always-on on Core, heavy on periphery

| App | Host | Why |
|---|---|---|
| Jotty | `core`, `edge` | File-based notes, tiny RAM, wanted when the HTPC is off |
| Linkding | `core`, `edge` | SQLite bookmarks, same |
| RustDesk `hbbs`/`hbbr` | `core`, host network | Rendezvous must be up whenever someone remotes in; host net so UDP 21116 sees real peer IPs |
| ZoneMinder | `periphery` | Capture + shm; Core cannot take this. Recordings are large and belong on NAS NFS |
| Adventure Log | `periphery` | PostGIS + ~1GB image; Core RAM is already tight |

**Alternative considered:** Adventure Log on Core. Rejected: PostGIS plus the aio image on a 4GB Pi next to OpenCloud/Gitea/Caddy.

**Alternative considered:** RustDesk on periphery. Rejected: HTPC sleep/off would drop ID/relay.

### 2. Jotty and Linkding: edge, no host ports

Same pattern as Vaultwarden/OpenCloud. Caddy `tls internal`, no `authelia_gate`.

| Host | Upstream |
|---|---|
| `notes.` `jotty.` | `jotty:3000` |
| `links.` `bookmarks.` `linkding.` | `linkding:9090` |

Jotty: `ghcr.io/fccview/jotty:latest`, `user: "${PUID}:${PGID}"`, `APP_URL=https://notes.${DOMAIN}`, `HTTPS=true`. Data at `${DATA_ROOT}/system/jotty/{data,config,cache}`. Admin is created in the first-run wizard (no Komodo secret).

Linkding: `sissbruecker/linkding:latest`, SQLite at `${DATA_ROOT}/system/linkding`. `LD_SUPERUSER_NAME` / `LD_SUPERUSER_PASSWORD` from Komodo. `LD_CSRF_TRUSTED_ORIGINS` lists the three HTTPS origins.

**Alternative considered:** Authelia proxy auth on Linkding. Rejected: edge gate is still off site-wide.

### 3. RustDesk OSS, LAN + WireGuard only

Official `rustdesk/rustdesk-server` with `network_mode: host` (same reason as wg-easy). Shared volume `${DATA_ROOT}/system/rustdesk` so `hbbs` and `hbbr` share `id_ed25519`. `hbbs` command: `hbbs -r ${NAS_LAN_IP}:21117` so the advertised relay is the NAS LAN address, not a Docker IP.

Do **not** attach to `edge`. Do **not** add `ports:` (host net). Do **not** document or add router forwards for 21115–21119. Caddy MUST NOT reverse-proxy those ports (the protocol is not HTTP; UDP 21116 cannot go through the existing Caddy HTTP vhosts).

Clients: ID server and relay = `desk.{$DOMAIN}` (Pi-hole wildcard already answers `NAS_LAN_IP`) **or** `NAS_LAN_IP`. Key = `id_ed25519.pub` from the data volume. Off-LAN: connect wg-easy first (client DNS is already `NAS_LAN_IP`).

Optional HTTPS page at `desk.` / `rustdesk.` with a static `respond` so Homepage has a live href. That is not a remote-desktop UI.

**Alternative considered:** Publish 21116/udp on the WAN so phones work without VPN. Rejected by the operator: off-LAN desktop is WireGuard.

**Alternative considered:** Bridge network + published ports. Rejected: hbbs NAT/heartbeat is unreliable unless it sees the real source IP; host net matches RustDesk’s Linux docs and this catalog’s WireGuard stack.

### 4. ZoneMinder on periphery, recordings on NFS

Image: `ghcr.io/zoneminder-containers/zoneminder-base:latest` (the stack that runs demo.zoneminder.com). MariaDB 11 beside it. `MYSQL_*` from Komodo `ZM_DB_PASSWORD` (app user and root, Immich-style single secret). `PUID`/`PGID` so NFS writes match household ACLs. `tmpfs` `/dev/shm` 1G.

| Volume | Where |
|---|---|
| MariaDB datadir | local HTPC volume |
| `/config`, `/log` | local HTPC volumes |
| `/data` (events) | `compose.yaml`: `${DATA_ROOT}/shared/cameras`; `compose.nfs.yaml`: Docker NFS `:${NFS_EXPORT}/cameras` |

Publish `8084:80`. Caddy: `cams.` `zm.` `zoneminder.` → `{$HTPC_UPSTREAM}:8084`. ResourceSync uses `compose.nfs.yaml` on this site.

Bootstrap creates `shared/cameras` with the same ACLs as other `shared/` trees. No new NFS export (still `/shared`).

**Alternative considered:** jantman/docker-zoneminder (go2rtc). Rejected: extra bind-mounted ini files and WebRTC ports; live view through Caddy HTTP is enough for first deploy.

**Alternative considered:** Recordings on HTPC local disk. Rejected: camera footage must sit on the NAS with the rest of household data (and move with IronWolf later).

### 5. Adventure Log standard (aio) on periphery

Official `ghcr.io/seanmorley15/adventurelog:latest` + `postgis/postgis:16-3.5`. `SITE_URL=https://travel.${DOMAIN}`. `POSTGRES_PASSWORD` and `DJANGO_ADMIN_PASSWORD` from Komodo. `DISABLE_REGISTRATION=True`. Publish `8015:80`. Local volumes for Postgres and media (like Immich DB — not NFS). Caddy: `travel.` `adventures.` `adventurelog.` → `{$HTPC_UPSTREAM}:8015`.

**Alternative considered:** Advanced frontend/backend split. Rejected: extra ports and env; Caddy already terminates TLS.

### 6. Homepage

Apps → Local: Jotty, Linkding, Adventure Log, ZoneMinder. System → Network: RustDesk (next to WireGuard). Public hrefs through Caddy. Core widgets by container name; HTPC `siteMonitor`/`container` on `periphery`.

### 7. Secrets (existing Core: add in Komodo, do not re-run bootstrap only for these)

| Key | Secret | Used by |
|---|---|---|
| `LINKDING_SUPERUSER_NAME` | | Linkding initial admin (default `admin`) |
| `LINKDING_SUPERUSER_PASSWORD` | secret | Linkding |
| `ZM_DB_PASSWORD` | secret | ZoneMinder MariaDB root + `zm` user |
| `ADVENTURELOG_POSTGRES_PASSWORD` | secret | PostGIS |
| `ADVENTURELOG_ADMIN_PASSWORD` | secret | Django admin on first boot |
| `ADVENTURELOG_ADMIN_EMAIL` | | Django admin email |

`core.sh` generates the secrets on new installs. Jotty and RustDesk have no Komodo secrets.

## Risks / Trade-offs

- **[RustDesk reachable on WAN if someone forwards 21115–21119 or enables UPnP]** → First-run doc: router forwards UDP 51820 only; disable UPnP for those ports. Catalog never publishes them through Caddy.
- **[hbbs advertises a wrong relay IP]** → `-r ${NAS_LAN_IP}:21117` is explicit.
- **[ZoneMinder shm too small / Docker Desktop]** → 1G tmpfs; first-run notes if live view fails.
- **[NFS event write latency]** → Events on NAS by design; DB stays local. Operator can lower FPS/retention in the UI.
- **[Adventure Log maps need outbound HTTPS]** → Expected; no extra catalog network policy.
- **[Core disk before IronWolf]** → App state is small except ZM events (`shared/cameras`). IronWolf move still later.

## Migration Plan

1. Add Komodo keys above. Run `data-root-perms.sh` (creates `system/{jotty,linkding,rustdesk}` and `shared/cameras`).
2. Push catalog; wait for ResourceSync. Deploy `jotty`, `linkding`, `rustdesk` on Core; Redeploy `caddy` and `homepage`. Deploy `zoneminder` and `adventurelog` on periphery. Open Windows firewall for 8084 and 8015 from the LAN.
3. First-run docs per app. RustDesk: copy public key, point clients at `desk.{$DOMAIN}`, test on LAN, then test through wg-easy with the WAN forwards **unchanged**.
4. Rollback: `deploy = false` or remove the new stacks; delete new volumes. Do not delete `shared/` household trees except `cameras` if unused.

## Open Questions

- None. Camera inventory and ZoneMinder monitor setup are operator first-run, not catalog.
