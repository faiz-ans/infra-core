## Context

This site is a two-host catalog today: Core is a Raspberry Pi CM5 (OMV, `DATA_ROOT` on the IronWolf, Docker, Komodo Core + local Periphery) and the TV PC is Windows (Docker Desktop, outbound Periphery as Komodo server `periphery`). After this rewrite the **names** are:

| Hostname | What it is |
|---|---|
| `core` | NAS (unchanged). Admin/`sudo`: `pilot`. |
| `surface` | Windows 11 TV PC. Admin: `pilot`. Daily/WSL owner: local user **`HTPC`**. Ethernet IPv4 is `SURFACE_UPSTREAM` (replaces `HTPC_UPSTREAM`). |
| `mantle` | Ubuntu WSL2 on `surface`. Linux user: `pilot`. Materia + Podman run here. `/etc/wsl.conf` `[network] hostname=mantle`. `.wslconfig` is `C:\Users\HTPC\.wslconfig`. |

Komodo `periphery` is retired. Materia `MANIFEST.toml` hosts are `core` and `mantle` only.

The catalog is Compose plus generated ResourceSync TOML. Site values live in Komodo. The operator is moving to Podman Quadlets, Materia GitOps, Cockpit on Core, and a Windows 11 `surface` with idle `mantle`. Kubernetes is a future consumer of the same YAML, not a runtime here.

Constraints already settled: no multi-host Deploy UI; split-privilege Core (rootless Caddy/Pi-hole/RustDesk/wg-easy UI; privileged nft + `wg0` + Scrutiny); Materia (not FetchIT; Ansible-pull deferred); sops per site/host; keep OMV (no CM5 re-flash); abandon OMV Compose and Docker NFS; household DNS/SSO/proxy/VPN stay.

## Goals / Non-Goals

**Goals:**

- One catalog language: kube-play subset YAML + Quadlet `.kube` for this site; reserved k8s overlay for later.
- Materia timer reconciles hosts from `MANIFEST.toml` and sops attributes.
- Repo tree matches that model; Komodo/Compose/Desktop-only files are gone.
- Core: purge Docker/Komodo on the existing OMV OS; Podman + Cockpit + Materia.
- Surface/`mantle`: documented Kodi + Firefox backup, wipe-install Windows 11, restore, idle WSL hostname `mantle` (no stacks).
- Same `DATA_ROOT` contract; mantle NFS is a WSL host mount.

**Non-Goals:**

- Running Kubernetes, ArgoCD, or Flux on this site.
- Re-flashing the CM5.
- FetchIT, Portainer, Podman Desktop, Docker Desktop.
- Playnite retirement, HA USB radios, Vaultwarden SMTP.
- Implementing the future production k8s overlay beyond a stub.

## Decisions

### 1. Shared contract is kube-play YAML; systemd is Quadlet

Portable unit: `Pod` / `ConfigMap` / `Secret` / `PVC` YAML that `podman kube play` accepts. This site wraps each app with a Quadlet `.kube` (`Yaml=`). A future ArgoCD/Flux site applies the same YAML plus `overlays/k8s/` (Service, Ingress, HPA). Host-netns rootless units (Caddy, Pi-hole, RustDesk, wg-easy UI) and host `wg-quick` MAY be `.container` / `.kube` Quadlets in the Podman tree only.

**Alternative considered:** Keep Compose and add kompose later. Rejected: not native for Materia or ArgoCD.  
**Alternative considered:** FetchIT kube method against the Podman socket. Rejected: live socket, not systemd-first.

### 2. Materia timer is the GitOps agent

Each host runs `materia update` on a systemd timer (root timer for nft/`wg-quick`/Scrutiny; user timer for rootless Quadlets). Materia reads git, selects components for the host, templates attributes, installs Quadlets, `daemon-reload`s, and starts units. It is a host binary, not a 24/7 container with `podman.sock` + D-Bus, and not `materia server`.

Host names in `MANIFEST.toml` are `core` and `mantle`. Bootstrap MUST set the Linux hostname (Core OS; WSL `/etc/wsl.conf`) to match. `surface` is the Windows computer name only; it MUST NOT appear as a Materia `[Hosts.*]` entry.

**Alternative considered:** Thin `git pull` + `daemon-reload` only. Rejected: no host assignment, no sops, no plan. Convenience of Materia is worth one timer.  
**Alternative considered:** FetchIT. Rejected: requires a live Podman socket.  
**Alternative considered:** ansible-pull. Deferred: more mature root binary, worse Quadlet plan/remove UX; keep Materia for now.

### 3. Sops/age attributes replace Komodo secrets

`attributes/vault.age` (shared non-secret defaults + encrypted secrets) and `attributes/core.age` / `attributes/mantle.age`. Age private key is created on the box and never committed. Changing a site is: edit that host file, encrypt, push. Example/unencrypted schema may live in git; live values must not. `SURFACE_UPSTREAM` is the IPv4 of `surface` (Caddy/NFS client).

Caddyfile keeps `{$VAR}` from container env. Homepage keeps `{{HOMEPAGE_VAR_*}}` from env injected by the Quadlet/template.

### 4. Repo layout (replace `stacks/` + `stacks/komodo/`)

```
MANIFEST.toml                 # host → components (replaces topology.inc + ResourceSync)
attributes/                   # sops vaults + README (no live plaintext secrets)
components/<app>/             # kube YAML, .kube, optional .container, config, MANIFEST.toml
overlays/k8s/README.md        # stub only
bootstrap/                    # Layer 0 (no komodo/, no docker engine scripts)
windows/                      # winget, cutover doc, steam-akl, scrutiny-collector
```

App config that today sits beside `compose.yaml` (Caddyfile, Homepage YAML, Authelia) moves into the component directory. `stacks/platform/`, `stacks/workload/`, and `stacks/komodo/` are removed after migration.

**Purge (no longer relevant):**

| Path | Why |
|---|---|
| `stacks/komodo/` | ResourceSync, fragments, generator |
| `bootstrap/komodo/` | Core compose, secret sync into Komodo |
| `bootstrap/core/core-docker-engine.sh` | dockerd log/pool |
| `bootstrap/periphery/periphery.compose.yaml` | Komodo Periphery |
| `bootstrap/periphery/periphery-docker-engine.ps1` | Docker Desktop engine |
| `bootstrap/periphery/periphery-nfs-rebind.ps1` | Docker NFS volume rebind |
| `bootstrap/periphery/htpc-recover.ps1` | Desktop/NFS recovery |
| `windows/docker-engine.json` | Desktop daemon.json |
| `stacks/platform/dockerproxy/` | Docker API for Homepage |
| Compose files as source of truth | Replaced by kube YAML |
| Homepage `config/docker.yaml` + Komodo widget keys | Engine-coupled UI |

**Keep (rewrite in place or move):** `bootstrap/omv/`, `data-root/`, `opencloud/`, `first-run/`, `core/core-lan-*.sh`, `core-fan.*`, `core-net.sh`, `htpc-lan-static.ps1` / `htpc-backup-drive.ps1` (rename toward `surface-*` and move `bootstrap/periphery/` to `bootstrap/mantle/` or `bootstrap/surface/`), `windows/steam-akl/`, `windows/scrutiny-collector/`, `windows/packages.json` (drop `Docker.DockerDesktop`).

### 5. Split privilege: rootless edge apps, privileged host plumbing only

Caddy, Pi-hole, and RustDesk do **not** run as rootful containers. Privileged ports and `wg0` stay on small **host** units.

| Rootful (host / audited) | Rootless (user Quadlet, host netns) |
|---|---|
| nft/iptables: LAN+WG `:80`/`:443` → Caddy high ports; `:53` → Pi-hole high port (extend `core-lan-bind`; listen on all ifaces, not DNAT-to-`127.0.0.1` then a userspace proxy) | Caddy (8080/8443 TCP+UDP), Pi-hole (e.g. 15353), RustDesk (`hbbs`/`hbbr` host-net 21115–21119, **no** port redirect), wg-easy UI (`:51821`) |
| WireGuard **data plane**: `wg0`, NAT, UDP 51820 (`wg-quick` or equivalent; not a rootless tun) | — |
| Scrutiny (SMART/devices) | Vaultwarden, Homepage, OpenCloud, and other Core apps |
| — | All mantle app stacks (including `pihole-mantle` with the same high-port + redirect idea) |

Redirects MUST preserve source addresses (REDIRECT/`DNAT` that stays in the host netns). Caddy and Pi-hole MUST bind the high ports on all interfaces so WireGuard clients (`wg0`) hit them. Do not DNAT Caddy or Pi-hole to `127.0.0.1` and then pasta/slirp/docker-proxy — that hides real client IPs. RustDesk stays host-net with no NAT hop so UDP 21116 still sees peer IPs.

WireGuard **clients** (phones/laptops) are unchanged: one tunnel, DNS `NAS_LAN_IP`, MTU 1280. The **client/peer UI** (wg-easy) is rootless; Caddy proxies it. Netbird is not used.

Two Materia instances (system timer for nft/`wg-quick`/Scrutiny; user timer for rootless Quadlets) on Core. Mantle Materia is user-level (`pilot` in WSL) unless a stack later needs root. The Windows user `HTPC` only owns the distro; it is not a Linux or Materia identity.

**Alternative considered:** Rootful Caddy/Pi-hole/RustDesk because they “need low ports / host net.” Rejected: low ports are a host redirect; RustDesk ports are already unprivileged; host-netns rootless preserves client IPs.  
**Alternative considered:** `ip_unprivileged_port_start=0` so Caddy binds 80/443 directly. Deferred: redirect matches existing DNS plumbing and does not let every local user bind 80.

### 6. Cockpit on Core only (required); mantle optional

Cockpit + `cockpit-podman` replaces Komodo’s restart/logs pane. Homepage + Glances + Uptime Kuma stay for “is it up?” Do not add Portainer.

### 7. Mantle is baseline WSL2 on surface, not Desktop

Windows 11 computer `surface`, `networkingMode=mirrored` so ports published in `mantle` are reachable at the Ethernet IP (`SURFACE_UPSTREAM`). Distro hostname `mantle`, systemd on, Linux user `pilot`. Podman from the distro. NVIDIA CDI inside WSL for GPU stacks. OMV `shared`/`users` mounted in WSL, then `hostPath` into pods. USB backup is `/mnt/d` (or the live drive letter), not Desktop file sharing.

**Alternative considered:** Podman Desktop. Rejected: extra VM, same class of tax as Docker Desktop.

### 8. Core transition is purge-and-redeploy, not a re-flash

Export Docker named volumes that are not already under `DATA_ROOT` (especially Caddy `/data`) onto `system/<app>/` or a tarball, then purge docker-ce, `/var/lib/docker`, `/etc/komodo`, `edge`/`docker0`, OMV Compose plugin. Install Podman/Cockpit/Materia. IronWolf and OMV stay.

### 9. Windows 11 wipe: save Kodi + Firefox, then idle WSL

Operator-facing procedure (catalog file `windows/kodi-firefox-cutover.md`). Do this **before** the clean install. Use an external disk or `Z:\` (NAS SMB), **not** `C:`.

**A. What to copy (entire folders)**

Quit Kodi and Firefox first.

| What | Copy this whole folder |
|---|---|
| Kodi (AKL, skins, menus, addons, sources) | `%APPDATA%\Kodi` |
| Firefox (all profiles, including the Kodi web-app profile) | `%APPDATA%\Mozilla\Firefox` |
| Steam→AKL helpers (if you installed them) | `C:\Utils\kodi-akl-steam-installed` (or wherever you put `windows/steam-akl`) |

In Explorer, paste `%APPDATA%` in the address bar to open the Roaming folder. Typical full paths:

```text
C:\Users\<you>\AppData\Roaming\Kodi
C:\Users\<you>\AppData\Roaming\Mozilla\Firefox
```

Copy each folder onto e.g. `Z:\htpc-win11-backup\` or a USB stick so you have:

```text
htpc-win11-backup\
  Kodi\
  Firefox\
  kodi-akl-steam-installed\     (optional)
```

Do **not** format the Restic USB (`D:`). Unplug it during the Windows install if you might pick the wrong disk. Do **not** format the NAS.

Optional check: after copy, `Kodi\userdata\addon_data` should exist (AKL lives there) and `Firefox\profiles.ini` plus `Firefox\Profiles\` should exist.

**B. Clean-install Windows 11**

1. Uninstall Docker Desktop on Win10 if it is still there (shrinks leftover WSL state). Not required if you are wiping `C:`.
2. Create a Windows 11 USB installer (Microsoft Media Creation Tool).
3. Boot the USB. When you reach disk selection, delete the **Windows** partitions on the **internal** disk only and install 11 there. Leave other disks (NAS is not this PC; USB backup should be unplugged).
4. Finish OOBE. Create Windows admin **`pilot`** and daily/WSL user **`HTPC`**. Set the computer name to **`surface`**. Kodi/Firefox `%APPDATA%` for the restored profiles is `C:\Users\HTPC\` if those apps run as `HTPC`.
5. Pin Ethernet on `surface` to `SURFACE_UPSTREAM` again (`bootstrap/periphery/htpc-lan-static.ps1` until renamed to `surface-*`) after the catalog rewrite lands; until then a DHCP lease is fine if the TV box can wait.

**C. Restore Kodi and Firefox**

1. `winget import -i windows\packages.json` (Docker Desktop will already be removed from that list) **or** install at least `XBMCFoundation.Kodi` and `Mozilla.Firefox`.
2. Quit Kodi and Firefox if the first launch created empty profiles.
3. Copy `htpc-win11-backup\Kodi` → `%APPDATA%\Kodi` (replace the new empty folder).
4. Copy `htpc-win11-backup\Firefox` → `%APPDATA%\Mozilla\Firefox` (replace).
5. Restore `C:\Utils\kodi-akl-steam-installed` if you use it. Map `Z:` to `\\<nas>\shared` again, then re-register the Steam sync task from `windows/steam-akl/`.
6. Open Kodi: AKL, skin, and menus should match. Open Firefox: the Kodi web-app profile should be in `about:profiles`.

**D. Idle WSL (no stacks)**

Do this logged in as Windows user **`HTPC`**. Create `C:\Users\HTPC\.wslconfig` (it does not exist until you write it):

```ini
[wsl2]
networkingMode=mirrored
hostAddressLoopback=true
```

Admin is only for `wsl --install --no-distribution` once. Install Ubuntu while logged in as `HTPC`. Linux user `pilot`. In the distro, `/etc/wsl.conf`:

```ini
[boot]
systemd=true
[user]
default=pilot
[network]
hostname=mantle
```

Then `wsl --shutdown`, reopen, confirm `hostname` is `mantle`, `wslinfo --networking-mode` is `mirrored`, `systemctl is-system-running` is `running`. Do **not** install Docker Desktop, Podman Desktop, or Materia stacks yet.

### 10. Homepage and monitoring

Public hrefs stay `https://<app>.{{HOMEPAGE_VAR_DOMAIN}}`. Internal scrapes stay container name on Core and `SURFACE_UPSTREAM` on mantle. Remove Docker socket-proxy and Komodo widgets. Glances + Uptime Kuma remain.

## Risks / Trade-offs

- **[Materia is a small project]** → Pin a known version; timer + Quadlets still run if Materia is paused; units are standard systemd.
- **[kube-play is a subset]** → Keep Ingress/Service/HPA out of Materia paths; host-only networking stays in Podman overlays.
- **[Caddy volume / other Docker-only state missed on purge]** → Inventory volumes before purge; copy Caddy `/data` to `system/caddy` (or equivalent) first.
- **[Win11 wipe loses unsaved Kodi/Firefox]** → Cutover doc is mandatory; copy whole Roaming folders, not “settings export.”
- **[Mirrored WSL + firewall]** → Document Windows + Hyper-V firewall for published ports when stacks return.
- **[Rootless + NFS]** → Mount NFS on the WSL host as the user (or root mount + `keep-id`), never a Docker NFS driver.
- **[Cockpit on a 4GB Pi]** → Core only; do not add Portainer.
- **[Public repo + sops]** → Age key stays on-box; never commit `keys.txt` or unencrypted vaults.
- **[Redirect hides client IPs or breaks WG DNS/HTTPS]** → Bind Caddy/Pi-hole high ports on all ifaces; REDIRECT in host netns; never DNAT-to-loopback plus proxy. Test LAN and a WG phone.
- **[wg-easy cannot drive `wg` if UI is rootless]** → Data plane is host `wg-quick`; UI only serves 51821. If wg-easy cannot manage peers without root, keep peer files on the host and treat the UI as read/config only, or split further during apply.

## Migration Plan

1. Land catalog rewrite on git (this change). Operators can already follow `windows/kodi-firefox-cutover.md`.
2. Surface: backup → wipe Win11 → restore Kodi/Firefox → idle `mantle`. Core stays Docker/Komodo so the house still has DNS/Caddy.
3. Core: export Docker volumes not on `DATA_ROOT` → purge Docker/Komodo → Podman + Cockpit + Materia → first apply (phase-equivalent: edge + OpenCloud first).
4. Mantle: WSL Podman, host NFS, user Materia as `pilot`, apply `[Hosts.mantle]` components.
5. Point Caddy at the same `SURFACE_UPSTREAM` ports. Confirm Authelia, Pi-holes, WG.
6. Rollback: Core can reinstall docker-ce and Komodo from the last git tag that still has `bootstrap/komodo/` **only if that tag is kept in history**. After purge, rollback is “re-apply old catalog from git + restore exported volumes.” Surface rollback of Windows is the backup folders + reinstall.

## Open Questions

- WSL distro: Ubuntu vs Fedora (either is fine; pick one in bootstrap docs during apply — default Ubuntu).
- Exact Materia install channel (release binary vs build) — pin during apply.
- Whether CaddyManager stays as an optional component (default: keep, `deploy` equivalent off until opted in).
