## Why

This repo is meant to be a public, environment-agnostic app catalog for a two-host homelab (Raspberry Pi NAS + Lenovo HTPC), but nothing in it yet deploys. Site values (domains, IPs, disk paths, secrets) must stay off GitHub, while compose and app config still have to land on the boxes without hand-copying files. Building the GitOps pipeline now—before the SATA hat and IronWolf replace the stand-in USB disk—means the catalog can survive that swap as a Komodo variable change rather than a rewrite.

## What Changes

- Add a public catalog layout: `stacks/platform`, `stacks/workload`, `stacks/komodo` (ResourceSync TOML), `bootstrap/`, and a `windows/` winget stub.
- Drive deploys on-site with Komodo (Core on the Pi, Periphery on both hosts). Komodo polls git; GitHub webhooks are not used.
- Keep all site identity in Komodo (variables/secrets written by bootstrap). Compose and configs in git use placeholders only (`${…}`, `{$…}`, `[[…]]`, `{{HOMEPAGE_VAR_…}}`).
- Bootstrap the Pi with an interactive script (OMV, Docker, Komodo Core + local Periphery) that prompts and writes secrets on the box; every command is also commented for manual use.
- Treat the HTPC as Docker Desktop (WSL2 engine), not docker-ce inside WSL2. A thin HTPC bootstrap brings up outbound Periphery as server `htpc`.
- Put a single Caddy on the Pi in front of both hosts; Authelia at the edge except Vaultwarden `/admin` only.
- Deploy NAS workloads (Homepage, Pi-hole, WireGuard, Vaultwarden, Restic client) and HTPC workloads (Home Assistant, Jellyfin, Arr, qBittorrent, Nextcloud, monitoring, Restic REST).
- Establish the `DATA_ROOT` directory contract (NAS uuid path locally; HTPC consumes the same tree over NFS; `BACKUP_DRIVE` for the 4TB USB).
- Add a winget export under `windows/` for later HTPC apps (Kodi, AHK, Firefox kiosk, Steam, emulators). Do not implement those Windows apps in this change.

## Capabilities

### New Capabilities
- `gitops-catalog`: Public compose/config catalog and in-git ResourceSync; no secrets, IPs, domains, or absolute disk paths in git; no GitHub webhooks.
- `nas-bootstrap`: Interactive Pi script that installs OMV, Docker, Komodo Core and local Periphery, and writes site secrets on disk.
- `htpc-runtime`: Docker Desktop as the HTPC engine; outbound Periphery `connect_as=htpc`; published ports on the Windows LAN IP (`HTPC_UPSTREAM`).
- `edge-access`: One Caddy on `nas`, Authelia, Pi-hole for `*.{$DOMAIN}`, WireGuard, and a shared Docker edge network.
- `homepage`: Templated `services.yaml` with public hrefs and internal widget/monitor URLs.
- `site-storage`: `DATA_ROOT` tree (`system/{core,periphery}`, `shared/{media,downloads,files,photos}`, `users/<user>/{files,photos}`) and per-host roots.
- `vaultwarden`: Vaultwarden on `nas`; Authelia on `/admin` only; data under `system/core/vaultwarden`.
- `backup`: NAS Restic client → HTPC Restic REST on `BACKUP_DRIVE`; include Vaultwarden data.
- `htpc-workloads`: Home Assistant (wifi/integrations), Jellyfin, Arr, qBittorrent, Nextcloud, Prometheus/Grafana on `htpc`, bound to the storage tree.
- `windows-winget`: Winget package list stub only; no Playnite/Kodi cutover.

### Modified Capabilities

- (none — no main specs exist yet)

## Impact

- New tree under `bootstrap/`, `stacks/`, and `windows/` in this public repo.
- Runtime: Raspberry Pi (OMV, Docker, Komodo Core/Periphery, edge and NAS stacks) and Windows 10 HTPC (Docker Desktop, Periphery, HTPC stacks, 4TB USB).
- External systems: GitHub (public clone/poll only), Komodo ResourceSync, OMV NFS for HTPC Docker, OMV SMB for interactive shares, Windows firewall for published ports.
- Out of scope for implementation: Kodi launcher, AHK, Firefox kiosk, Steam, emulators, HA radios, share-name polish, SMTP for Vaultwarden.
