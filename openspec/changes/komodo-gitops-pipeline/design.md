## Context

`infra-core` is an empty public GitHub repo intended as the app catalog for a two-host site: a Raspberry Pi CM5 NAS (4GB, Raspberry Pi OS Lite 64-bit, OMV, stand-in USB disk until an IronWolf on a SATA HAT arrives) and a Windows 10 Legion HTPC (always-on behind a TV) that will run Docker Desktop. Komodo is the on-site orchestrator. GitHub webhooks are forbidden because the catalog is public and deploys must not depend on inbound GitHub.

Site values (domain, IPs, `DATA_ROOT`, secrets) must not live in git. Config files (Caddyfile, Homepage YAML) must still deploy with the stack.

This design implements the `komodo-gitops-pipeline` proposal and specs.

## Goals / Non-Goals

**Goals:**

- Reproducible GitOps: clone catalog → fill Komodo → sync.
- One Caddy on the Pi for `*.{$DOMAIN}`; Authelia at the edge with the Vaultwarden `/admin` exception and Komodo (`ops`) serving its own login.
- NAS + HTPC stacks up, including backup to the HTPC 4TB USB.
- Pi bootstrap that prompts and writes secrets on-box.

**Non-Goals:**

- Playnite → Kodi launcher, AHK, Firefox kiosk, Steam, emulator config (winget list only).
- Home Assistant USB radios.
- Renaming `shared/` / `users/` after real use.
- Vaultwarden SMTP.
- Putting Komodo Core on the HTPC.

## Decisions

### 1. Three layers: bootstrap, Komodo, catalog

Komodo cannot install itself through ResourceSync on an empty Pi.

| Layer | Where | Role |
|---|---|---|
| 0 | `bootstrap/core.sh` (+ thin `bootstrap/periphery`) | OMV, Docker, Core, first Periphery; prompt/write secrets |
| 1 | Komodo DB + Core/Periphery `[secrets]` | Only store of live values |
| 2 | This git repo | Compose, config templates, ResourceSync TOML |

**Alternative considered:** Ansible or a private repo with values. Rejected: operator wants a public catalog and Komodo on-site.

### 2. ResourceSync in git, servers onboarded not committed

`stacks/komodo/*.toml` declares stacks with literal `server = "core"` or `"periphery"` (Komodo does not interpolate `[[VAR]]` on `server`/`repo`), `repo` + `run_directory`, and `environment` keys mapped to `[[VARS]]`. Bootstrap `CORE_SERVER` / `PERIPHERY_SERVER` must match those literals. Server resources are created by onboarding (bootstrap / Periphery `connect_as`). IPs never appear in TOML. Stack names are unique across both files (`pihole` vs `pihole-periphery`).

**Alternative considered:** UI-only stacks pointing at git folders. Rejected: a dead Pi would lose topology; ResourceSync is the reproduce path.

### 3. Interpolation split

Komodo interpolates the stack `environment` block (`[[VAR]]`) and writes `.env` for Compose (`${VAR}`). It does not rewrite random files in git.

- Caddyfile: native `{$VAR}`.
- Homepage: `{{HOMEPAGE_VAR_…}}` from container env (Komodo copies `[[DOMAIN]]` → `HOMEPAGE_VAR_DOMAIN`, etc.).
- Compose volume paths: `${DATA_ROOT}/shared/media` (relative contract in git; absolute root in Komodo).

**Alternative considered:** `pre_deploy` envsubst on every config. Rejected unless an app has no native env syntax.

### 4. Core on Pi, HA and media on HTPC, Docker Desktop on Windows 10

Core stays on the NAS so the control plane survives the TV box rebooting. HA moves to HTPC for RAM. Docker Desktop publishes ports on the Windows LAN IP, so `HTPC_UPSTREAM` is that IP—no `netsh portproxy`.

HTPC Periphery runs as a Desktop container (docker.sock mounted) in **outbound** mode to Core (`PERIPHERY_CORE_ADDRESS`). Windows NAT is then irrelevant for agent control.

**Alternative considered:** docker-ce inside a user WSL distro. Rejected: Win10 NAT and changing WSL IPs. **Alternative considered:** Core on WSL2. Rejected: operator lock.

### 5. One Caddy, shared `edge` network, Pi-hole wildcard

On `nas`, external network `edge` attaches Caddy, Authelia, Homepage, Pi-hole, WireGuard, Vaultwarden. Caddy routes:

- local: `vaultwarden:80`, Homepage, Pi-hole admin, Komodo, OMV as applicable
- remote: `{$HTPC_UPSTREAM}:<published port>` for Jellyfin, HA, Nextcloud, Arr, Grafana, Restic REST (if exposed)

Pi-hole: `*.{$DOMAIN}` → NAS LAN IP. WireGuard on NAS for remote access to that same DNS/Caddy path.

**Alternative considered:** second Caddy on HTPC. Rejected: splits Authelia. **Alternative considered:** Homepage Docker label discovery. Rejected: Homepage cannot see HTPC sockets; templated YAML is required.

### 6. Homepage href vs widget

Public href: `https://<app>.{{HOMEPAGE_VAR_DOMAIN}}` (Caddy + Authelia). Internal scrape: NAS `http://<container>:<port>`; HTPC `http://{{HOMEPAGE_VAR_HTPC_UPSTREAM}}:<port>`. Ports may be literals in git.

### 7. Vaultwarden Authelia matcher

`pw.{$DOMAIN}`: `forward_auth` only for `/admin` and `/admin/*`. `/api/*`, `/icons/*`, `/events/*`, `/notifications/*`, and the web vault are Vaultwarden’s own auth so official clients work.

### 8. Storage and backup

```
${DATA_ROOT}/system/<app>/            # authelia, vaultwarden, pihole, wireguard, restic
${DATA_ROOT}/shared/{media,downloads,files,photos}
${DATA_ROOT}/users/<user>/{files,photos}
```
HTPC `/config` is a local Docker volume, not under `DATA_ROOT`.

- `nas` `DATA_ROOT` = OMV `/srv/dev-disk-by-uuid-*`
- `htpc` app stacks = Docker NFS volumes of `shared/` and `users/` (`NAS_LAN_IP` + `NFS_EXPORT` + `NFS_USERS`)
- SMB: household Explorer/Finder only; not the Docker bind path
- `BACKUP_DRIVE` = HTPC 4TB USB; Restic REST lives there
- NAS restic client → REST on `HTPC_UPSTREAM`; include `system/vaultwarden`

IronWolf swap = change `DATA_ROOT` on `nas` (and remount on HTPC), not a git commit.

### 9. Repo and stack layout

```
bootstrap/core.sh
bootstrap/periphery.md + periphery.compose.yaml
stacks/platform/{caddy,authelia,pihole,wireguard,homepage,restic,restic-rest,monitoring}/
stacks/workload/{vaultwarden,jellyfin,seerr,arr,qbittorrent,nextcloud,homeassistant}/
stacks/komodo/{stacks-core.toml,stacks-periphery.toml}
windows/winget.json                     # stub
```

Komodo Core compose used by bootstrap may be vendored under `bootstrap/` so Layer 0 does not depend on ResourceSync.

### 10. Suggested published ports (catalog literals)

| Service | Port (container/host as published on HTPC or NAS local) |
|---|---|
| Jellyfin | 8096 |
| Home Assistant | 8123 |
| Nextcloud | 443 or 8080 (choose one in compose; Caddy upstream matches) |
| qBittorrent | 8080 (if not colliding) |
| Arr apps | conventional 8989/7878/… |
| Grafana | 3000 |
| Restic REST | 8000 |
| Vaultwarden | 80 on `edge` only (not published to LAN if Caddy is the door) |

Exact non-colliding host ports are an implementation detail; Caddyfile and Homepage must share the same Komodo-injected `HTPC_UPSTREAM` plus these catalog ports.

## Risks / Trade-offs

- **[Pi 4GB still busy with OMV + Core + edge]** → Keep HA/media off the Pi; monitor memory; avoid extra NAS stacks.
- **[Windows Firewall blocks Caddy → Desktop ports]** → HTPC bootstrap documents/allows the published port list.
- **[Docker Desktop file sharing vs SMB bind mounts]** → Do not bind SMB/NFS drive letters. HTPC app stacks use the Docker NFS volume driver (`NAS_LAN_IP` + `NFS_EXPORT` + `NFS_USERS`). SMB remains for Explorer/Finder.
- **[WSL2/Desktop not running]** → HTPC workloads and restic REST are down; Core on Pi still up. Acceptable for an always-on HTPC.
- **[Authelia vs widgets]** → Internal URLs avoid SSO on scrapes; hrefs stay protected.
- **[Public ResourceSync TOML shows topology]** → Acceptable; no secrets. Repo name `owner/infra-core` in TOML is catalog identity, not site secret.
- **[OMV uuid changes on disk swap]** → `DATA_ROOT` variable; bootstrap re-detect.
- **[Vaultwarden API unauthenticated at proxy]** → Relies on VW account auth + `SIGNUPS_ALLOWED=false` after first user; Authelia still gates `/admin`.

## Migration Plan

1. Commit catalog + bootstrap (this change) to the public repo.
2. SCP `bootstrap/core.sh` to the Core host; run (or follow comments). Confirm Core UI, server `core` (or `CORE_SERVER` override), variables present.
3. ResourceSync poll: platform stacks (Caddy, Authelia, Pi-hole, WireGuard), then Homepage, Vaultwarden, restic client.
4. On the HTPC: Docker Desktop, NFS from OMV (not SMB drive letters), attach USB, run thin Periphery bootstrap, open firewall ports.
5. Confirm the periphery server connected; sync periphery stacks; point Caddy upstreams at `HTPC_UPSTREAM`.
6. Create first Vaultwarden user; set signups false; confirm clients sync and `/admin` requires Authelia.
7. When IronWolf arrives: migrate OMV disk, update Core `DATA_ROOT`, keep the same NFS share name, redeploy—no catalog rewrite.

Rollback: disable ResourceSync auto-apply; `docker compose down` per stack on the affected server; Core remains via bootstrap compose. Git revert of catalog plus Komodo sync returns topology to the previous commit.

## Open Questions

- Nextcloud host port vs TLS-inside-container (Caddy vs Nextcloud TLS) — pick during compose so Caddy’s upstream is HTTP or HTTPS consistently.
- Arr stack membership beyond Sonarr/Radarr (Prowlarr, Bazarr, etc.) — start with Sonarr + Radarr + Prowlarr. qBittorrent is its own stack.
