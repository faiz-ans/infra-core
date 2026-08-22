## ADDED Requirements

### Requirement: Docker Desktop is the HTPC engine
HTPC Compose stacks SHALL run on Docker Desktop for Windows, using WSL2 as Docker’s backend. They MUST NOT require docker-ce (or equivalent) installed inside a user WSL2 distro as the orchestrated engine.

#### Scenario: Publish on the Windows LAN IP
- **WHEN** an HTPC stack publishes a port
- **THEN** that port is reachable at the laptop’s LAN IP (`HTPC_UPSTREAM`) without `netsh portproxy` or a WSL2-eth0 address

### Requirement: Outbound Periphery on the remote host
A thin remote bootstrap SHALL start Komodo Periphery (typically as a Docker Desktop container with the engine socket mounted) in outbound mode to Core, with `connect_as` equal to `PERIPHERY_SERVER` (default `periphery`). Core MUST NOT need an inbound connection to the remote OS for agent control. The bootstrap SHALL prompt for values the engine needs (Core address, onboarding key, `BACKUP_DRIVE`) and write them on the box.

#### Scenario: Periphery dials Core
- **WHEN** HTPC Periphery starts with Core reachable on the LAN
- **THEN** Komodo shows the `PERIPHERY_SERVER` (default `periphery`) connected without exposing Periphery’s listen port through Windows NAT

### Requirement: NAS data visible to Desktop
HTPC app stacks SHALL mount the OMV DATA_ROOT tree using either catalog `compose.yaml` (`DATA_ROOT` bind: local disk or a host NFS/SMB mount) or `compose.nfs.yaml` (Docker NFS driver: `NAS_LAN_IP` + `NFS_EXPORT`). They MUST NOT bind a Windows SMB or NFS drive letter as `DATA_ROOT`. SMB MAY remain for interactive file copy. `BACKUP_DRIVE` SHALL be the 4TB USB volume used by Restic REST and MUST be a separate variable from the NAS tree.

#### Scenario: Same tree, two transports
- **WHEN** Jellyfin on `htpc` mounts `${NFS_EXPORT}/shared/media` over NFS
- **THEN** that path is the household media tree from OMV, not a directory on the laptop’s internal SSD
