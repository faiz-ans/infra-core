## REMOVED Requirements

### Requirement: Interactive Core bootstrap script
**Reason**: `core.sh` / `site.env` prompts are replaced by GET scaffold + desired `site.yaml`.
**Migration**: Day 0 GET A, then edit desired, then SET.

### Requirement: OMV owns the data disk mount
**Reason**: OpenMediaVault is not supported.
**Migration**: native-storage SET mounts by UUID.

### Requirement: OMV install must not steal the SSH session
**Reason**: OMV is removed.
**Migration**: None.

### Requirement: OMV workbench does not occupy HTTP/HTTPS
**Reason**: OMV is removed.
**Migration**: Ingress host binds Caddy high ports; lan-bind redirects `:80/:443`.

### Requirement: Komodo Core is not a catalog chicken-egg
**Reason**: Komodo is not a deploy path.
**Migration**: Ansible SET.

### Requirement: Keep OMV, do not re-flash by default
**Reason**: OMV is removed; hosts are existing Debian/Ubuntu.
**Migration**: GET/SET against already-imaged OS disks.

### Requirement: Purge Docker and Komodo
**Reason**: This change is not a Docker-to-Podman cutover playbook.
**Migration**: Operator images or uses a clean Debian/Ubuntu if Docker remains.

### Requirement: Install Podman, Cockpit, and Materia
**Reason**: Materia is removed; Cockpit/Podman are SET from topology.
**Migration**: `operations.host.manager` and `operations.workload.engine`.

### Requirement: Layer 0 does not install Materia
**Reason**: Materia is removed entirely.
**Migration**: None.

### Requirement: Layer 0 stops before apply and before lan-bind
**Reason**: There is no `core.sh` Layer 0.
**Migration**: SET enables lan-bind only after Caddy and Pi-hole listeners exist (catalog-templates / edge-access).

## ADDED Requirements

### Requirement: Existing ext4 data disk is not formatted
SET MUST NOT format an ext4 disk that desired identifies by UUID. Empty or non-ext4 handling, if any, MUST be an explicit desired action, not a default.

#### Scenario: Populated UUID is mounted
- **WHEN** desired names an existing ext4 UUID as a storage drive
- **THEN** SET mounts it and does not run `mkfs`

### Requirement: Host LAN address may be static
When desired lists a host `ip`, SET MAY configure a static IPv4 on that host’s uplink so the address matches inventory. SET MUST NOT change the address if doing so would drop the active Ansible SSH session without a fallback.

#### Scenario: SSH session preserved
- **WHEN** the live address already equals desired `ip`
- **THEN** SET does not rewrite the interface address
