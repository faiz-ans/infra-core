## 1. Core stacks

- [x] 1.1 Add `stacks/workload/jotty/compose.yaml` (edge, PUID, APP_URL, DATA_ROOT binds)
- [x] 1.2 Add `stacks/workload/linkding/compose.yaml` (edge, SQLite, CSRF origins, Komodo superuser)
- [x] 1.3 Add `stacks/workload/rustdesk/compose.yaml` (host net, shared keys volume, hbbs `-r NAS_LAN_IP:21117`)
- [x] 1.4 Register `jotty`, `linkding`, and `rustdesk` in `stacks-core.toml`

## 2. Periphery stacks

- [x] 2.1 Add Adventure Log compose (aio + PostGIS, SITE_URL, local volumes, 8015)
- [x] 2.2 Register `adventurelog` in `stacks-periphery.toml`

## 3. Edge, Homepage, secrets

- [x] 3.1 Caddyfile: Jotty, Linkding, Adventure Log vhosts; RustDesk static hint at `desk.` / `rustdesk.`
- [x] 3.2 Homepage tiles for Jotty, Linkding, RustDesk, and Adventure Log
- [x] 3.3 Document and wire Komodo keys in `VARIABLES.md` and `core.sh`

## 4. Bootstrap and first-run

- [x] 4.1 Create `system/{jotty,linkding,rustdesk}` in `data-root-perms.sh` / README
- [x] 4.2 Add `bootstrap/{jotty,linkding,rustdesk,adventurelog}.md`; update `periphery.md` firewall ports

## 5. Drop ZoneMinder

- [x] 5.1 Remove ZoneMinder compose, ResourceSync, Caddy, Homepage, secrets, bootstrap, and `shared/cameras` from the catalog
