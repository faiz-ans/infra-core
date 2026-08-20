## ADDED Requirements

### Requirement: Docker Desktop is the HTPC engine
HTPC Compose stacks SHALL run on Docker Desktop for Windows, using WSL2 as Docker’s backend. They MUST NOT require docker-ce (or equivalent) installed inside a user WSL2 distro as the orchestrated engine.

#### Scenario: Publish on the Windows LAN IP
- **WHEN** an HTPC stack publishes a port
- **THEN** that port is reachable at the laptop’s LAN IP (`HTPC_UPSTREAM`) without `netsh portproxy` or a WSL2-eth0 address

### Requirement: Outbound Periphery as htpc
A thin HTPC bootstrap SHALL start Komodo Periphery (typically as a Docker Desktop container with the engine socket mounted) in outbound mode to Core on the NAS, with `connect_as=htpc`. Core MUST NOT need an inbound connection to Windows for agent control. The bootstrap SHALL prompt for values the engine needs (Core address, onboarding key, Docker Desktop-visible `DATA_ROOT` / NAS share path, `BACKUP_DRIVE`) and write them on the box.

#### Scenario: Periphery dials Core
- **WHEN** HTPC Periphery starts with Core reachable on the LAN
- **THEN** Komodo shows server `htpc` connected without exposing Periphery’s listen port through Windows NAT

### Requirement: NAS data visible to Desktop
`DATA_ROOT` on `htpc` SHALL be a Docker Desktop-visible mount of the same OMV tree used on `nas` (SMB or equivalent persistent mapping). `BACKUP_DRIVE` SHALL be the 4TB USB volume used by Restic REST and MUST be a separate variable from `DATA_ROOT`.

#### Scenario: Same tree, two roots
- **WHEN** Jellyfin on `htpc` mounts `${DATA_ROOT}/shared/media`
- **THEN** that path is the household media share from OMV, not a directory on the laptop’s internal SSD
