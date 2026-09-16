# mantle (Ubuntu WSL2 on surface)

Linux user: `pilot`. Windows owner: `HTPC` (`C:\Users\HTPC\.wslconfig`). Hostname in `/etc/wsl.conf` is `mantle`.

Idle state (already done on this site): mirrored networking, systemd, hostname `mantle`. Do **not** install Docker Desktop or Podman Desktop.

## After Core is on Podman

1. Install distro Podman and lingering as `pilot`.
2. Mount OMV NFS in WSL (not a Docker NFS driver, not `Z:` as DATA_ROOT):

   ```bash
   sudo mkdir -p /mnt/nas/shared /mnt/nas/users
   sudo mount -t nfs -o nfsvers=4 ${NAS_LAN_IP}:/shared /mnt/nas/shared
   sudo mount -t nfs -o nfsvers=4 ${NAS_LAN_IP}:/users /mnt/nas/users
   ```

   Persist in `/etc/fstab`. Attributes: `NFS_SHARED=/mnt/nas/shared`, `NFS_USERS=/mnt/nas/users`, `BACKUP_DRIVE=/mnt/d`.

3. NVIDIA: current Windows NVIDIA driver + WSL NVIDIA Container Toolkit CDI (`nvidia.com/gpu=all`).
4. Age key + Materia **v0.7.2** user timer as `pilot` (`materia update`, not `materia server`). Hostname must be `mantle`.
5. Windows + Hyper-V firewall: allow published ports on `SURFACE_UPSTREAM` (8096, 53, 61208, 8000, …).

Smoke: `podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi`

USB SMART still uses [`windows/scrutiny-collector/`](../../windows/scrutiny-collector/).
