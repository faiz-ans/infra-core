## ADDED Requirements

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
