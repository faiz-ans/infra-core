## 1. Surface Windows 11 cutover (operator can run before catalog apply)

- [x] 1.1 Add `windows/kodi-firefox-cutover.md` with the backup (`%APPDATA%\Kodi`, `%APPDATA%\Mozilla\Firefox`, optional `C:\Utils\kodi-akl-steam-installed`), wipe-install (internal disk only, unplug Restic USB), restore, identities (`pilot` admin, Windows user `HTPC` owns WSL), and idle-`mantle` steps from the design (`C:\Users\HTPC\.wslconfig`, `/etc/wsl.conf` hostname `mantle`, mirrored + systemd, no stacks)
- [x] 1.2 Point `windows/README.md` at that doc, steam-akl, and scrutiny-collector; stop mentioning Docker Desktop engine JSON
- [x] 1.3 Remove `Docker.DockerDesktop` from `windows/packages.json`

## 2. Catalog skeleton

- [x] 2.1 Add root `MANIFEST.toml` assigning current topology stacks to `core` / `mantle` (bootstrap vs full as comments or roles); omit `dockerproxy`; do not list `surface` as a Materia host
- [x] 2.2 Add `attributes/README.md` plus example vault/host schemas (no live secrets); document age key on-box; host files `core.age` / `mantle.age`; catalog var `SURFACE_UPSTREAM`
- [x] 2.3 Add `overlays/k8s/README.md` stub stating Materia must not apply this path
- [x] 2.4 Add component directory convention (`MANIFEST.toml`, kube YAML, `.kube`, config files) and pin Materia install/version in bootstrap docs

## 3. Move apps into components (kube YAML + Quadlets)

- [x] 3.1 Convert Core edge: Caddy, Authelia, Pi-hole, Glances, PeaNUT, Homepage (rootless host-netns Caddy/Pi-hole + source-preserving `:80`/`:443`/`:53` redirects; Podman network for Authelia/Homepage; `host.containers.internal` or localhost instead of `host.docker.internal`)
- [x] 3.2 Convert OpenCloud (Core) and Collabora (`mantle`); keep DATA_ROOT binds / first-run order
- [x] 3.3 Convert remaining Core apps: WireGuard data plane (`wg-quick` rootful) + wg-easy UI (rootless host-netns), Vaultwarden, Jotty, Linkding, BentoPDF, IT Tools, ByteStash, RustDesk (rootless host-net, no redirect), Scrutiny (rootful), Uptime Kuma, CaddyManager (optional), Restic client. Do not ship Gitea; catalog origin is the operator’s git remote (this site: GitHub).
- [x] 3.4 Convert mantle media: Jellyfin, Seerr, Arr, qBittorrent (hostPath from WSL NFS, local config volumes, CDI GPU where needed)
- [x] 3.5 Convert remaining mantle apps: Immich, Adventure Log, Scriberr, Transmute, LibreTranslate, OpenReader, n8n, Frigate, Home Assistant, glances-mantle, pihole-mantle, monitoring, restic-rest
- [x] 3.6 Inject `HOMEPAGE_VAR_*` and Caddy `{$VAR}` from attributes; drop Komodo `[[VAR]]` / ResourceSync `environment` blocks; `HOMEPAGE_VAR_SURFACE_UPSTREAM` replaces `HTPC_UPSTREAM`
- [x] 3.7 Do not convert `dockerproxy`; Homepage must not reference Docker or Komodo widgets

## 4. Purge old repo structure

- [x] 4.1 Delete `stacks/komodo/` (topology, fragments, generator, ResourceSync TOML, VARIABLES.md)
- [x] 4.2 Delete `bootstrap/komodo/` (Core compose, secret sync into Komodo)
- [x] 4.3 Delete `bootstrap/core/core-docker-engine.sh`, `bootstrap/periphery/periphery.compose.yaml`, `periphery-docker-engine.ps1`, `periphery-nfs-rebind.ps1`, `htpc-recover.ps1`, `windows/docker-engine.json`
- [x] 4.4 Delete `stacks/platform/dockerproxy/` and Homepage `config/docker.yaml`
- [x] 4.5 Remove `stacks/platform/` and `stacks/workload/` after components own their config (no leftover compose.yaml / compose.nfs.yaml as source of truth)
- [x] 4.6 Rewrite root `README.md` for Materia layers (bootstrap → attributes/Materia → components) and names `core` / `surface` / `mantle`

## 5. Core bootstrap (purge + Podman)

- [x] 5.1 Rewrite `bootstrap/core.sh` to install Podman (system + user lingering as `pilot`), Cockpit + cockpit-podman, Materia timers, age key; stop installing Docker and Komodo
- [x] 5.2 Add purge steps: export Docker volumes not on DATA_ROOT (document Caddy `/data`), then remove docker-ce, `/var/lib/docker`, `/etc/komodo`, Docker networks, OMV Compose plugin
- [x] 5.3 Keep `data-root-prep.sh` / `layout` / OpenCloud / OMV / LAN / fan scripts; remove Docker-only assumptions (`docker0` avahi deny, `docker exec` in OpenCloud helpers → `podman exec`)
- [x] 5.4 Split-privilege: system units for nft redirects, `wg-quick`, Scrutiny; user Quadlets for Caddy, Pi-hole, RustDesk, wg-easy UI, and the rest of Core apps; extend `core-lan-bind` so Caddy/Pi-hole bind all ifaces (real client IPs, LAN+WG)

## 6. Surface / mantle bootstrap (idle WSL → later stacks)

- [x] 6.1 Rename `bootstrap/periphery/` to match the new names (e.g. `bootstrap/mantle/` for WSL + keep Windows scripts under `windows/` or `bootstrap/surface/`). Rewrite README for Win11 `surface`, Windows user `HTPC`, Linux `pilot`, mirrored WSL hostname `mantle`, systemd, distro Podman, host NFS mounts, CDI GPU, `/mnt/d` backup, firewall (Windows + Hyper-V if needed)
- [x] 6.2 Replace Komodo Periphery compose with Materia user timer as `pilot` + age key + hostname `mantle`
- [x] 6.3 Keep `htpc-lan-static.ps1` and `htpc-backup-drive.ps1` (rename to `surface-*` if paths move); pin Ethernet to `SURFACE_UPSTREAM`; retarget backup smoke tests from Docker Desktop binds to WSL paths

## 7. Docs and first-run

- [x] 7.1 Rewrite `bootstrap/README.md`, `bootstrap/omv/README.md` (host NFS, drop Docker NFS driver / `insecure` rationale if WSL uses reserved ports), NUT/`host.containers.internal`
- [x] 7.2 Rewrite `bootstrap/first-run/*.md` (Komodo Deploy → Materia apply / systemd; `docker` → `podman`; drop Komodo secret UI steps)
- [x] 7.3 Document Cockpit on Core; no required mantle Cockpit; no `ops.` Komodo vhost in Caddyfile
- [x] 7.4 Cutover order in README: `surface` wipe / idle `mantle` while Core still serves DNS/Caddy → Core purge/apply → mantle Materia apply

## 8. Verification

- [x] 8.1 `openspec validate --change podman-rewrite` (or equivalent) and grep that purged paths are gone
- [x] 8.2 Confirm no plaintext secrets/IPs/domains in `components/` / `MANIFEST.toml`
- [x] 8.3 Confirm `overlays/k8s/` is not referenced by Materia host assignment
- [x] 8.4 Confirm catalog/docs use `core` / `surface` / `mantle` and `SURFACE_UPSTREAM`; no live Materia host named `periphery`
