## ADDED Requirements

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
