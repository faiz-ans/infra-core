## ADDED Requirements

### Requirement: DATA_ROOT tree
On the NAS data disk, the following directory contract SHALL exist (created by bootstrap or first deploy). Names are a starting contract and MAY be renamed in a later change:

```
${DATA_ROOT}/
  system/
    core/
    periphery/
  shared/
    media/
    downloads/
    files/
    photos/
  users/
    <user>/
      files/
      photos/
```

#### Scenario: Tree creation
- **WHEN** NAS bootstrap or an initial storage task runs
- **THEN** `system/core`, `system/periphery`, `shared/{media,downloads,files,photos}`, and a documented pattern for `users/<user>/{files,photos}` exist under `DATA_ROOT`

### Requirement: Workloads bind the tree via variables
Jellyfin, Arr, qBittorrent, and Nextcloud SHALL mount subdirectories of this tree. Catalog `compose.yaml` uses `${DATA_ROOT}/...` bind mounts (local disk, host NFS, or host SMB/CIFS). Catalog `compose.nfs.yaml` uses Docker NFS volumes of `${NFS_EXPORT}/...` on `NAS_LAN_IP`. ResourceSync SHALL list exactly one of those files per stack. Shared household content uses `shared/`; per-user Nextcloud files and Memories use `users/<user>/files` and `users/<user>/photos`.

#### Scenario: Media and photos mounts
- **WHEN** Jellyfin and Nextcloud stacks are deployed
- **THEN** Jellyfin uses `${DATA_ROOT}/shared/media` and Nextcloud can access both `${DATA_ROOT}/shared/{files,photos}` and `${DATA_ROOT}/users/<user>/{files,photos}`

### Requirement: Host-specific roots only
The absolute `DATA_ROOT` path SHALL be a Komodo variable on `nas` (the OMV uuid mount, e.g. under `/srv/dev-disk-by-uuid-*`). HTPC app stacks SHALL mount the same tree over NFS using `NAS_LAN_IP` and `NFS_EXPORT` (the OMV shared-folder NFSv4 path). They MUST NOT bind a Windows SMB or NFS drive letter. The 4TB USB backup target SHALL be a separate HTPC variable (`BACKUP_DRIVE`) and MUST NOT be required to live under `DATA_ROOT`.

#### Scenario: Disk swap
- **WHEN** the OMV data disk UUID path changes
- **THEN** updating `DATA_ROOT` on Core (and keeping the same NFS shared-folder name) is sufficient for stacks to use the new disk without editing committed compose files

#### Scenario: Restic REST storage
- **WHEN** Restic REST runs on `htpc`
- **THEN** its repository path uses `BACKUP_DRIVE` (the USB volume), not `shared/media`

### Requirement: Permission boundaries
NAS-only app state SHALL live under `${DATA_ROOT}/system/core`. HTPC app state for Jellyfin, qBittorrent, and Nextcloud SHALL live under `${DATA_ROOT}/system/periphery` via NFS. Arr `/config` on Docker Desktop SHALL be a local volume (SQLite on NFS is unusable); media and downloads stay on NFS. Home Assistant `/config` on Docker Desktop SHALL be a local volume with the catalog `configuration.yaml` bind-mounted (NFS file overlays drop `trusted_proxies`). Household content SHALL live under `shared/` and `users/`. SMB MAY remain for interactive Explorer/Finder access.

#### Scenario: HTPC NFS mount
- **WHEN** the HTPC Docker engine mounts OMV NFS at `${NFS_EXPORT}/system/periphery` and `${NFS_EXPORT}/shared`
- **THEN** it can persist Nextcloud, Jellyfin, and qBittorrent config under `system/periphery` and write household data under `shared/` and `users/`
