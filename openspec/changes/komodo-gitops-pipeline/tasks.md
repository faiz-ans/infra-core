## 1. Catalog skeleton

- [x] 1.1 Create `stacks/platform/`, `stacks/workload/`, `stacks/komodo/`, `bootstrap/`, and `windows/` directories with `.gitkeep` or first real files
- [x] 1.2 Add a root README section describing Layer 0/1/2, server names `nas`/`htpc`, and that site values live only in Komodo
- [x] 1.3 Document the Komodo variable/secret key list (no values) used across stacks (`DOMAIN`, `HTPC_UPSTREAM`, `DATA_ROOT`, `BACKUP_DRIVE`, `NAS_LAN_IP`, Homepage and Vaultwarden keys)

## 2. NAS bootstrap

- [x] 2.1 Add `bootstrap/` Komodo Core compose (and Periphery) used only for first start, independent of ResourceSync
- [x] 2.2 Write `bootstrap/core.sh` that prompts (domain default `home.lan`, Core LAN IP, remote Periphery upstream, passwords/tokens, confirm detected `DATA_ROOT`) and writes Core/Periphery `[secrets]`
- [x] 2.3 In `core.sh`, install OMV (if external disk), Docker, start Core + local Periphery, onboard `CORE_SERVER` (default `core`), create `DATA_ROOT` tree, configure ResourceSync poll with webhooks off
- [x] 2.4 Comment every bootstrap command in `core.sh` for manual copy-paste

## 3. HTPC runtime

- [x] 3.1 Add `bootstrap/` Periphery compose for Docker Desktop (socket mount, outbound `PERIPHERY_CORE_ADDRESS`, `connect_as=htpc`)
- [x] 3.2 Add `bootstrap/periphery.md` (or script) covering Docker Desktop, OMV NFS for app data, SMB for interactive copy, `BACKUP_DRIVE`, firewall ports, onboarding key prompt/write
- [x] 3.3 Add `windows/` winget list including Docker Desktop plus Kodi, AHK, Firefox, Steam, Dolphin, ePSXe, PCSX2 (list only)

## 4. ResourceSync

- [x] 4.1 Write `stacks/komodo/stacks-nas.toml` declaring NAS stacks with `server = "nas"`, git `run_directory` paths, `[[VAR]]` env keys, `after` ordering, webhooks disabled
- [x] 4.2 Write `stacks/komodo/stacks-htpc.toml` the same for `htpc`
- [x] 4.3 Ensure TOML contains no IPs, domain literals, uuid paths, or secret values

## 5. Edge on nas

- [x] 5.1 Define external Docker network `edge` and attach Caddy, Authelia, Pi-hole, WireGuard, Homepage, Vaultwarden
- [x] 5.2 Add `stacks/platform/caddy/` compose + Caddyfile using `{$DOMAIN}` and `{$HTPC_UPSTREAM}`; include Vaultwarden site with Authelia only on `/admin` and `/admin/*`
- [x] 5.3 Add `stacks/platform/authelia/` compose and config templates with Komodo-injected secrets (no users/passwords in git)
- [x] 5.4 Add `stacks/platform/pihole/` compose; local DNS for `*.{$DOMAIN}` via env, not committed IPs
- [x] 5.5 Add `stacks/platform/wireguard/` compose with keys/endpoint from Komodo

## 6. Homepage and Vaultwarden

- [x] 6.1 Add `stacks/workload/homepage/` compose and templated `services.yaml` (public hrefs, internal widget/monitor URLs, `{{HOMEPAGE_VAR_…}}`)
- [x] 6.2 Map Komodo `[[DOMAIN]]` and `[[HTPC_UPSTREAM]]` (and widget keys) into `HOMEPAGE_VAR_*` in the Homepage stack environment
- [x] 6.3 Add `stacks/workload/vaultwarden/` compose with `${DATA_ROOT}/system/vaultwarden`, edge network, env for URL/admin token/signups from Komodo

## 7. Backup

- [x] 7.1 Add `stacks/workload/restic/` client on `nas` targeting REST on `HTPC_UPSTREAM`, including `${DATA_ROOT}/system/vaultwarden`
- [x] 7.2 Add `stacks/workload/restic-rest/` on `htpc` with data on `${BACKUP_DRIVE}`

## 8. HTPC workloads

- [x] 8.1 Add Jellyfin stack mounting `${DATA_ROOT}/shared/media`, published port matching Caddy/Homepage
- [x] 8.2 Add qBittorrent + Arr (Sonarr, Radarr, Prowlarr) stacking `${DATA_ROOT}/shared/media` and `shared/downloads`
- [x] 8.3 Add Nextcloud stack mounting `shared/{files,photos}` and `users` tree
- [x] 8.4 Add Home Assistant stack (wifi/integrations only) with published port matching Caddy
- [x] 8.5 Add Prometheus + Grafana stack; Grafana proxied via Caddy; scrape targets as Komodo vars

## 9. Sanity

- [x] 9.1 Grep the catalog (excluding `bootstrap/core.sh` prompt default) for leaked `home.lan`, RFC1918 literals, uuid paths, and password assignments
- [x] 9.2 Update README with bootstrap order: Pi script → ResourceSync NAS → HTPC Desktop/Periphery → ResourceSync HTPC
