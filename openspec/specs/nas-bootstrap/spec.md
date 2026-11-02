## Purpose

TBD

## Requirements

### Requirement: Pre-GitOps software on the Pi
Bootstrap SHALL install OpenMediaVault (when using an external data disk), Docker, Komodo Core, and a local Komodo Periphery, then onboard a Komodo server named `CORE_SERVER` (default `core`). When using an external disk it SHALL mount it at the OMV uuid path and use that as `DATA_ROOT`. When using the OS disk it SHALL use a directory such as `/srv/core`. It SHALL create the `DATA_ROOT` directory contract (`system/<app>` for Core app state, `shared/{media,downloads,files,photos}`, `users/`). It MUST NOT create `system/core` or `system/periphery`. When OMV is installed it SHALL export `shared/` and `users/` over NFS to the HTPC LAN IP and MUST NOT export the disk root or `system/`. After Core is up, it SHALL print ResourceSync setup for this public repo with webhooks off.

#### Scenario: Fresh Pi OS Lite
- **WHEN** bootstrap completes on Raspberry Pi OS Lite 64-bit with an OMV data disk attached
- **THEN** Docker, Komodo Core, and Periphery are installed, the Core server resource exists under `CORE_SERVER` (default `core`), `DATA_ROOT` uses `system/<app>` (not `system/core`), NFS exports `shared/` and `users/` to the HTPC IP, and ResourceSync poll instructions are available

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

### Requirement: Thin DATA_ROOT prep unchanged in spirit
Greenfield prep SHALL still create `${DATA_ROOT}/system` and empty `users/` (plus OpenCloud host dirs) before edge/OpenCloud come up. Full household layout SHALL still wait until after OpenCloud publish. This rewrite MUST NOT recreate `system/core`, `system/periphery`, `system/surface`, or `system/mantle`.

#### Scenario: Prep does not require Komodo
- **WHEN** `data-root-prep.sh` runs
- **THEN** it does not write Komodo config and does not require Docker

### Requirement: Existing ext4 data disk is not formatted
SET MUST NOT format an ext4 disk that desired identifies by UUID. Empty or non-ext4 handling, if any, MUST be an explicit desired action, not a default.

#### Scenario: Populated UUID is mounted
- **WHEN** desired names an existing ext4 UUID as a storage drive
- **THEN** SET mounts it and does not run `mkfs`

### Requirement: Secret prompts do not steal stdin
Site-secret collection SHALL NOT read the secret list from the same stdin that `read -p` uses for operator prompts. Answers and `site.env` SHALL be written under `/etc/infra-core`. Paths and helpers named for Komodo (`/etc/komodo`, `komodo_*`) MUST NOT be required.

#### Scenario: Prefill answers keep DOMAIN
- **WHEN** `/etc/infra-core/bootstrap-answers.env` already contains `DOMAIN` and `NAS_LAN_IP`
- **THEN** those values appear unchanged in `/etc/infra-core/site.env` after secret collection

### Requirement: Host LAN address may be static
When desired lists a host `ip`, SET MAY configure a static IPv4 on that host’s uplink so the address matches inventory. SET MUST NOT change the address if doing so would drop the active Ansible SSH session without a fallback.

#### Scenario: SSH session preserved
- **WHEN** the live address already equals desired `ip`
- **THEN** SET does not rewrite the interface address
