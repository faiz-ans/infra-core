## Why

This site’s GitOps plane is Docker Compose plus Komodo (Postgres, FerretDB, Core, two Periphery agents). That is heavier and less isolated than Podman Quadlets under systemd, blocks a native path to a future Kubernetes/ArgoCD catalog, and ties the Windows box to Docker Desktop. The Windows 11 wipe is happening now, so the catalog and Layer 0 bootstrap must match the new runtime and **host names** before stacks come back.

## What Changes

- **BREAKING:** Host names drop Komodo `periphery`. This site is:

  | Role | Hostname | OS / who runs GitOps |
  |---|---|---|
  | NAS | `core` | Raspberry Pi OS + OMV; Materia on Core |
  | Windows TV PC | `surface` | Windows 11; Kodi; Ethernet LAN IP (`SURFACE_UPSTREAM`) |
  | Container engine | `mantle` | Ubuntu WSL2 on `surface`; Materia + Podman |

  Admin login on `core`, `surface`, and `mantle` is **`pilot`**. WSL is owned by the Windows local user **`HTPC`** (not `pilot`); inside Ubuntu the user is `pilot`. `.wslconfig` lives in `C:\Users\HTPC\`. `MANIFEST.toml` assigns workloads to `core` and `mantle` only (`surface` is not a Materia host).

- **BREAKING:** Replace Docker + Komodo GitOps with Podman + systemd Quadlets. Shared app contract is Kubernetes YAML that `podman kube play` accepts. A future K8s site applies the same YAML plus a k8s-only overlay (Ingress, Service, HPA). This site never runs Kubernetes.
- **BREAKING:** Materia (timer, not a long-lived socket container) assigns components to `core` / `mantle`, templates attributes, installs Quadlets, and reconciles systemd. FetchIT is not used. Site values stay off plaintext git via sops/age per host (`attributes/core.age`, `attributes/mantle.age`). Catalog var `HTPC_UPSTREAM` becomes **`SURFACE_UPSTREAM`** (IPv4 of `surface`). Second Pi-hole / Glances instances are `pihole-mantle` / `glances-mantle`, not `*-periphery`.
- **BREAKING:** Restructure the repo for that catalog (Materia `MANIFEST.toml`, `components/`, `attributes/`, kube YAML + `.kube` units). Purge Komodo ResourceSync, Compose-only trees, Docker Desktop engine files, and other artifacts that only exist for the old plane.
- Core: keep the OMV OS (no CM5 re-flash). Purge Docker/Komodo leftovers, install Podman, Cockpit, and Materia. `DATA_ROOT` and OMV shares stay. Split privilege: rootful only for audited host plumbing (nft port redirects, WireGuard `wg0`/NAT, Scrutiny). **Caddy, both Pi-holes, RustDesk, and the WireGuard client/UI (wg-easy on 51821) run rootless** in the host netns so they still see real client IPs. Do not bind Caddy/Pi-hole to privileged ports inside a rootful container; host REDIRECT/DNAT maps `:80`/`:443` and `:53` to their high ports (same idea as today’s `core-lan-bind`). FetchIT and Ansible-pull were considered; Materia stays.
- Surface: Windows 11 clean install (wipe). Document save/restore of Kodi userdata (AKL, skins, menus) and the Firefox profile used for Kodi web apps, then idle `mantle` (mirrored networking, systemd, hostname `mantle`, no stacks until the catalog is ready). No Docker Desktop or Podman Desktop.
- Edge function stays: one Caddy, Authelia, paired Pi-holes, WireGuard, off-LAN via WG. Homepage keeps templated hrefs; Docker/Komodo widgets and socket-proxies go. Cockpit on Core is the container/systemd GUI; mantle Cockpit is optional.
- Storage: mantle uses WSL host NFS mounts + `hostPath`, not the Docker NFS volume driver. OMV Compose plugin is abandoned.
- Household app images stay unless they exist only to serve Docker/Komodo (socket-proxy, Komodo itself).

## Capabilities

### New Capabilities

- `gitops-catalog`: Public kube-play YAML + Quadlet wrappers + Materia host manifest; no secrets/IPs/domains in plaintext git; no Compose/ResourceSync; k8s overlay path reserved but unused here.
- `materia-gitops`: Per-host Materia timer; plan/execute; sops attributes; root and user Quadlet dirs; no FetchIT.
- `nas-bootstrap`: Core stays on existing OMV; purge Docker/Komodo; install Podman, Cockpit, Materia; write age key and site attributes on-box.
- `htpc-runtime`: Win11 `surface` + WSL2 `mantle` (user `pilot`, Windows owner `HTPC`); mirrored publish on `SURFACE_UPSTREAM`; host NFS; CDI GPU; no Desktop engines.
- `htpc-windows-cutover`: Operator steps to back up Kodi + Firefox, wipe-install Windows 11, restore those profiles, and leave WSL idle.
- `edge-access`: Same DNS/SSO/proxy/VPN behavior. Rootless host-netns Caddy/Pi-hole/RustDesk plus rootless WireGuard UI; privileged host nft redirects and WireGuard data plane only.
- `site-storage`: Same `DATA_ROOT` contract; host NFS/bind instead of Docker NFS; mantle `/config` stays local (Podman volumes).
- `homepage`: Templated public hrefs and internal monitors; no Docker API or Komodo widgets.
- `cockpit-ui`: Cockpit + cockpit-podman on Core for unit/container inspect and restart.
- `windows-winget`: Winget list without Docker Desktop; Kodi/Firefox/Steam/emulators remain; cutover docs live under `windows/`.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs)

## Impact

- Repo: replace `stacks/komodo/` and Compose-as-source with Materia components; delete Docker Desktop / Komodo / socket-proxy catalog files; rewrite `bootstrap/`, root `README.md`, and first-run docs.
- Core runtime: OMV unchanged; Docker and Komodo removed; Podman + Materia + Cockpit added.
- Surface/mantle: Windows 11 wipe; Kodi/Firefox restored; idle `mantle` until apply; later Podman stacks and host NFS.
- External: git poll of the catalog remote (this site: GitHub); no on-box git forge; no Komodo; no GitHub webhooks; OMV NFS/SMB remain; Windows firewall (and Hyper-V firewall if mirrored WSL needs it).
- Out of scope: implementing a live Kubernetes site, Playnite retirement, HA USB radios, SMTP for Vaultwarden, re-flashing the CM5.
