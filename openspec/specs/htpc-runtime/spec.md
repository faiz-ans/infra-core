## Purpose

TBD

## Requirements

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
HTPC app stacks SHALL mount household data using either catalog `compose.yaml` (`DATA_ROOT` bind: local disk or a host NFS/SMB mount) or `compose.nfs.yaml` (Docker NFS driver: `NAS_LAN_IP` + `NFS_EXPORT` + `NFS_USERS`). They MUST NOT bind a Windows SMB or NFS drive letter as `DATA_ROOT`. SMB MAY remain for interactive file copy. `BACKUP_DRIVE` SHALL be the 4TB USB volume used by Restic REST and MUST be a separate variable from the NAS tree.

#### Scenario: Same tree, two transports
- **WHEN** Jellyfin on `htpc` mounts `${NFS_EXPORT}/media` over NFS
- **THEN** that path is the household media tree from OMV, not a directory on the laptop’s internal SSD

### Requirement: Baseline WSL2 is the mantle engine
Catalog stacks for the TV PC SHALL run in Ubuntu WSL2 hostname **`mantle`** on Windows computer **`surface`**, using distro-packaged Podman and systemd, Linux user **`pilot`**. The Windows local user **`HTPC`** SHALL own the distro (`C:\Users\HTPC\.wslconfig`). They MUST NOT require Docker Desktop or Podman Desktop.

#### Scenario: No Desktop engine
- **WHEN** a mantle stack is applied
- **THEN** it is a Podman Quadlet (or kube play under systemd) inside WSL, not a Docker Desktop project

### Requirement: Mirrored networking publishes on SURFACE_UPSTREAM
WSL SHALL use mirrored networking so ports published in `mantle` are reachable at `surface`’s Ethernet LAN IP (`SURFACE_UPSTREAM`) without `netsh portproxy` and without using a NAT-only WSL eth0 address as the Caddy upstream.

#### Scenario: Caddy reaches Jellyfin
- **WHEN** Jellyfin publishes 8096 in WSL under mirrored mode
- **THEN** Caddy on Core can proxy to `SURFACE_UPSTREAM:8096` on the LAN

### Requirement: Host NFS, not Docker NFS
Mantle app stacks SHALL consume OMV `shared/` and `users/` via NFS mounts performed in WSL (then `hostPath` or equivalent into pods). They MUST NOT use the Docker NFS volume driver or bind a Windows SMB drive letter as `DATA_ROOT`. SMB MAY remain for Explorer/Kodi. `BACKUP_DRIVE` SHALL remain a separate USB path visible in WSL (e.g. `/mnt/d`).

#### Scenario: Jellyfin library on NAS
- **WHEN** Jellyfin is deployed
- **THEN** its library path is the OMV `shared/media` tree via the WSL NFS mount, not the laptop internal SSD

### Requirement: GPU via CDI
Stacks that need the NVIDIA GPU SHALL request it through CDI (`nvidia.com/gpu=all` or equivalent), not Compose `deploy.resources` device reservations. The Windows NVIDIA driver plus WSL NVIDIA Container Toolkit CDI generation SHALL be documented in surface/mantle bootstrap.

#### Scenario: Immich ML sees the GPU
- **WHEN** CDI is generated and the Immich ML unit requests the GPU device
- **THEN** `nvidia-smi` inside that container lists the GPU on `surface`
