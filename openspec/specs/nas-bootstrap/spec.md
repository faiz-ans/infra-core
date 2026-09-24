## Purpose

TBD

## Requirements

### Requirement: Interactive Core bootstrap script
The catalog SHALL include a bootstrap script intended to be copied onto the Core host (for example via SCP). The script SHALL prompt for site values (including domain, with default `home.lan` as the prompt default only, this host’s LAN IP, remote Periphery upstream IP, Komodo admin password, Vaultwarden admin token, and confirmation of detected `DATA_ROOT`) and SHALL write those values only to on-box Komodo Core and/or Periphery secret/config files—not into the git catalog. Each action SHALL also appear as commented copy-paste commands for manual use.

#### Scenario: Prompt and write
- **WHEN** an operator runs the NAS bootstrap and answers prompts
- **THEN** secrets and site values exist on the Pi in Komodo config and are not written into repository files

#### Scenario: Manual fallback
- **WHEN** the operator prefers not to run the script unattended
- **THEN** the same install and write steps are available as comments inside the script

### Requirement: Pre-GitOps software on the Pi
Bootstrap SHALL install OpenMediaVault (when using an external data disk), Docker, Komodo Core, and a local Komodo Periphery, then onboard a Komodo server named `CORE_SERVER` (default `core`). When using an external disk it SHALL mount it at the OMV uuid path and use that as `DATA_ROOT`. When using the OS disk it SHALL use a directory such as `/srv/core`. It SHALL create the `DATA_ROOT` directory contract (`system/<app>` for Core app state, `shared/{media,downloads,files,photos}`, `users/`). It MUST NOT create `system/core` or `system/periphery`. When OMV is installed it SHALL export `shared/` and `users/` over NFS to the HTPC LAN IP and MUST NOT export the disk root or `system/`. After Core is up, it SHALL print ResourceSync setup for this public repo with webhooks off.

#### Scenario: Fresh Pi OS Lite
- **WHEN** bootstrap completes on Raspberry Pi OS Lite 64-bit with an OMV data disk attached
- **THEN** Docker, Komodo Core, and Periphery are installed, the Core server resource exists under `CORE_SERVER` (default `core`), `DATA_ROOT` uses `system/<app>` (not `system/core`), NFS exports `shared/` and `users/` to the HTPC IP, and ResourceSync poll instructions are available

### Requirement: OMV owns the data disk mount
When using an external data disk, bootstrap SHALL register the ext4 filesystem with OpenMediaVault (`FileSystemMgmt.setMountPoint`) and apply the fstab module so the volume appears in Storage → File Systems. Bootstrap MUST NOT leave only a Debian `/etc/fstab` UUID line: that hides the disk from the OMV Mount UI and blocks shared folders. A plain fstab mount is allowed only if the OMV RPC is unavailable or fails.

#### Scenario: Shared folders can use DATA_ROOT
- **WHEN** bootstrap has mounted the external disk as `DATA_ROOT`
- **THEN** the same UUID is an OMV mount-point object and the fstab line lives in the `[openmediavault]` tagged block

### Requirement: OMV install must not steal the SSH session
When bootstrap installs OpenMediaVault over SSH, it SHALL invoke the vendor install script with skip-network (`-n`) and skip-reboot (`-r`) so the installer does not purge NetworkManager, rewrite systemd-networkd, or reboot. After the installer returns, bootstrap SHALL verify an IPv4 default route still exists before continuing.

#### Scenario: Installer keeps DHCP
- **WHEN** bootstrap runs the OMV installer on a host that already has a working LAN address
- **THEN** that address remains reachable over SSH when the installer finishes, and the host is not rebooted by the vendor script

### Requirement: OMV workbench does not occupy HTTP/HTTPS
When OpenMediaVault is installed, bootstrap SHALL move the OMV workbench off host ports 80 and 443 so Caddy can bind them. The workbench HTTP listen port SHALL be taken from the OMV configuration database (`conf.webadmin.port`), not from `OMV_NGINX_SITE_WEBGUI_LISTEN_PORT`. After the change, workbench SHALL listen on port 81 and OMV SHALL NOT terminate TLS on 443.

#### Scenario: Caddy can bind 80 and 443
- **WHEN** bootstrap has installed OMV and applied the workbench port change
- **THEN** host nginx listens on 81 (not 80/443) and Caddy can publish `80:80` and `443:443`

### Requirement: Komodo Core is not a catalog chicken-egg
Komodo Core (and the first local Periphery) SHALL be brought up by bootstrap, not by ResourceSync. After Core exists, ResourceSync MAY manage other stacks. Bootstrap MAY later adopt Core as a visible stack but MUST remain able to start Core without Komodo already running.

#### Scenario: Empty box
- **WHEN** Komodo is not yet running on the Pi
- **THEN** bootstrap can still install and start Core without pulling a stack through ResourceSync

### Requirement: Core LAN address is static
After site prompts, bootstrap SHALL pin `NAS_LAN_IP` as a NetworkManager manual IPv4 address on the uplink NIC (gateway from the live default route, DNS left to systemd-resolved). It MUST NOT depend on a router DHCP reservation for Core to return after a reboot or cold plug. It MUST NOT change the address if `NAS_LAN_IP` does not already match the live uplink (SSH would drop). Re-running bootstrap SHALL be idempotent when the profile already matches. A router DHCP reservation MAY still exist; it is not the source of truth for the NAS address.

#### Scenario: Cold plug without a DHCP lease
- **WHEN** bootstrap has pinned `NAS_LAN_IP` and Core is power-cycled (USB NIC included)
- **THEN** that address is on the uplink without waiting for DHCPOFFER, and SSH to `NAS_LAN_IP` works

### Requirement: Host forwarding and WireGuard operator hints
Bootstrap SHALL persist IPv4 forwarding on Core (`net.ipv4.ip_forward=1`) so host-network WireGuard can NAT. It SHALL prompt for `WG_HOST` as a public endpoint name (not a LAN name) and SHALL print operator steps for UDP 51820-only forwarding, keeping `DOMAIN` from swallowing `WG_HOST` in Pi-hole, and confirming client MTU 1280 after the first WireGuard deploy. Live values SHALL stay on-box.

#### Scenario: Printed WireGuard steps
- **WHEN** bootstrap finishes
- **THEN** the operator is told to forward only the WireGuard UDP port to Core, use a public `WG_HOST`, and confirm MTU 1280 before issuing peers

### Requirement: Thin DATA_ROOT prep before phase A

NAS/Core bootstrap SHALL create `${DATA_ROOT}/system` and an empty `${DATA_ROOT}/users` parent (plus OpenCloud host directories under `system/opencloud`) via the prep script before phase-A OpenCloud Deploy. It MUST NOT require creating household `users/<name>` trees or the full `shared/` protected layout before OpenCloud space roots exist. Full household layout and NFS/SMB export of `shared/` and `users/` SHALL occur after OpenCloud publish (phase-B readiness), per bootstrap-phases.

#### Scenario: Bootstrap stops short of household layout

- **WHEN** Core bootstrap prep completes on a greenfield data disk
- **THEN** `system/` and empty `users/` exist and household media layout under `shared/` has not yet been mandated by prep

### Requirement: Keep OMV, do not re-flash by default
NAS/Core bootstrap for this rewrite SHALL run on the existing Raspberry Pi OS + OMV install. It MUST NOT require re-imaging the CM5. The IronWolf `DATA_ROOT` mount and OMV SMB/NFS shares SHALL remain the data plane.

#### Scenario: Data disk survives
- **WHEN** Docker and Komodo have been purged and Podman bootstrap has run
- **THEN** `${DATA_ROOT}/system`, `shared/`, and `users/` are still present on the same uuid mount

### Requirement: Purge Docker and Komodo
Core bootstrap SHALL stop catalog stacks and Komodo, then remove docker-ce/containerd/Compose plugin packages, `/var/lib/docker`, `/etc/komodo`, Docker bridges (`docker0`, `edge` as a Docker network), and Docker iptables/nft leftovers. OMV Compose plugin SHALL be removed or left unused. Before purge, operators SHALL be instructed to copy Docker named volumes that are not already under `DATA_ROOT` (including Caddy data) onto the data disk or a tarball.

#### Scenario: No dockerd after bootstrap
- **WHEN** the purge phase completes
- **THEN** `dockerd` is not running and `/etc/komodo` is absent

### Requirement: Install Podman, Cockpit, and Materia
Core bootstrap SHALL install Podman (system and user, lingering enabled for catalog user **`pilot`**), Cockpit with cockpit-podman, and Materia, create an age key, and write Materia source URL plus attribute paths on-box. It SHALL prompt for site values and write them into encrypted attributes or an on-box env file, not into git.

#### Scenario: Layer 0 without Komodo
- **WHEN** bootstrap finishes on Core
- **THEN** Podman, Cockpit, and a Materia timer exist and Komodo Core/Periphery/Postgres/FerretDB containers are not required

### Requirement: Thin DATA_ROOT prep unchanged in spirit
Greenfield prep SHALL still create `${DATA_ROOT}/system` and empty `users/` (plus OpenCloud host dirs) before edge/OpenCloud come up. Full household layout SHALL still wait until after OpenCloud publish. This rewrite MUST NOT recreate `system/core`, `system/periphery`, `system/surface`, or `system/mantle`.

#### Scenario: Prep does not require Komodo
- **WHEN** `data-root-prep.sh` runs
- **THEN** it does not write Komodo config and does not require Docker

### Requirement: Layer 0 does not install Materia
Core bootstrap (`core.sh`) SHALL install Podman (system and user, lingering enabled for `pilot`), Cockpit with cockpit-podman, and write site values to on-box files under `/etc/infra-core` (not into git). It MUST NOT install a Materia binary, Materia systemd timers, or `/etc/materia` as a required path. It MUST NOT require Docker or Komodo to be present, and MUST NOT require a Docker/Komodo purge to complete.

#### Scenario: Layer 0 without GitOps poller
- **WHEN** `core.sh` finishes on a new OS
- **THEN** `podman` and Cockpit are present, `/etc/infra-core/site.env` exists, and `materia` is not required on `PATH`

### Requirement: Existing ext4 data disk is not formatted
If an extra disk already has an ext4 filesystem, bootstrap SHALL mount and register it as `DATA_ROOT`. It MUST NOT offer format unless there is no ext4 and the operator types `YES`. If a `/srv/dev-disk-by-uuid-*` path is already mounted, that mount SHALL be `DATA_ROOT`.

#### Scenario: Pre-mounted uuid is used
- **WHEN** `/srv/dev-disk-by-uuid-<uuid>` is already a mount of the site data disk
- **THEN** `core.sh` sets `DATA_ROOT` to that path and does not run `mkfs`

### Requirement: Layer 0 stops before apply and before lan-bind
`core.sh` SHALL run thin `data-root-prep` only (not full household `shared/` layout), SHALL leave `core-lan-bind` disabled, SHALL NOT export NFS, and SHALL NOT apply catalog components. Host DNS during Layer 0 SHALL use public resolvers until Pi-hole listens.

#### Scenario: Done message does not enable redirects
- **WHEN** `core.sh` prints Done
- **THEN** `:53`/`:80`/`:443` host REDIRECT is not enabled and NFS exports have not been written by this run

### Requirement: Secret prompts do not steal stdin
Site-secret collection SHALL NOT read the secret list from the same stdin that `read -p` uses for operator prompts. Answers and `site.env` SHALL be written under `/etc/infra-core`. Paths and helpers named for Komodo (`/etc/komodo`, `komodo_*`) MUST NOT be required.

#### Scenario: Prefill answers keep DOMAIN
- **WHEN** `/etc/infra-core/bootstrap-answers.env` already contains `DOMAIN` and `NAS_LAN_IP`
- **THEN** those values appear unchanged in `/etc/infra-core/site.env` after secret collection
