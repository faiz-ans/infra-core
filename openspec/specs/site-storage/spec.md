## Purpose

TBD

## Requirements

### Requirement: DATA_ROOT tree
On the NAS data disk, the following directory contract SHALL exist (created by bootstrap or first apply). Names MAY match the current site:

```
${DATA_ROOT}/
  system/<app>/
  shared/{media,downloads,files,photos,cameras}
  users/<user>/{files,photos}
```

NAS-only app state SHALL live under `system/<app>`. Household content SHALL stay under `shared/` and `users/`. Bootstrap MUST NOT create `system/core`, `system/periphery`, `system/surface`, or `system/mantle`.

#### Scenario: Tree present after engine swap
- **WHEN** Core has moved from Docker to Podman
- **THEN** existing `system/`, `shared/`, and `users/` trees are still the bind/NFS sources for apps

### Requirement: Workloads bind the tree via variables
Jellyfin, Arr, qBittorrent, and Nextcloud SHALL mount household subdirectories of this tree. `/config` for those apps (and Home Assistant) SHALL be a local Docker volume on the HTPC, not under `DATA_ROOT`. Catalog `compose.yaml` uses `${DATA_ROOT}/...` bind mounts for household data (local disk, host NFS, or host SMB/CIFS). Catalog `compose.nfs.yaml` uses Docker NFS volumes of `${NFS_EXPORT}/...` (the OMV `shared` export) and `${NFS_USERS}` (the OMV `users` export) on `NAS_LAN_IP`. ResourceSync SHALL list exactly one of those files per stack. Shared household content uses `shared/`; per-user Nextcloud files and Memories use `users/<user>/files` and `users/<user>/photos`.

#### Scenario: Media and photos mounts
- **WHEN** Jellyfin and Nextcloud stacks are deployed
- **THEN** Jellyfin uses `${DATA_ROOT}/shared/media` and Nextcloud can access both `${DATA_ROOT}/shared/{files,photos}` and `${DATA_ROOT}/users/<user>/{files,photos}`

### Requirement: Host-specific roots only
The absolute `DATA_ROOT` path SHALL be a Komodo variable on `nas` (the OMV uuid mount, e.g. under `/srv/dev-disk-by-uuid-*`). HTPC app stacks SHALL mount household trees over NFS using `NAS_LAN_IP`, `NFS_EXPORT` (OMV `shared` share), and `NFS_USERS` (OMV `users` share). They MUST NOT be given an NFS export of the disk root or of `system/`. They MUST NOT bind a Windows SMB or NFS drive letter. The 4TB USB backup target SHALL be a separate HTPC variable (`BACKUP_DRIVE`) and MUST NOT be required to live under `DATA_ROOT`.

#### Scenario: Disk swap
- **WHEN** the OMV data disk UUID path changes
- **THEN** updating `DATA_ROOT` on Core (and keeping the same NFS shared-folder name) is sufficient for stacks to use the new disk without editing committed compose files

#### Scenario: Restic REST storage
- **WHEN** Restic REST runs on `htpc`
- **THEN** its repository path uses `BACKUP_DRIVE` (the USB volume), not `shared/media`

### Requirement: Permission boundaries
NAS-only app state SHALL live under `${DATA_ROOT}/system/<app>` (Authelia, Vaultwarden, Pi-hole, WireGuard, restic). HTPC `/config` for Jellyfin, Arr, qBittorrent, Nextcloud, and Home Assistant SHALL be local volumes so those apps can start if Core/NFS is down. Home Assistant SHALL bind-mount the catalog `configuration.yaml` (NFS file overlays drop `trusted_proxies`). Household content (media, downloads, Nextcloud files/photos/users) SHALL stay on NFS under `shared/` and `users/`. Bootstrap MUST NOT create `system/core` or `system/periphery`. SMB MAY remain for interactive Explorer/Finder access.

#### Scenario: HTPC NFS mount
- **WHEN** the HTPC Docker engine mounts OMV NFS at `${NFS_EXPORT}` (`/shared`) and `${NFS_USERS}` (`/users`)
- **THEN** it can write household data under `shared/` and `users/`

### Requirement: Mantle local config, NAS for libraries
Mantle `/config` (or equivalent) SHALL be a local Podman volume so apps can start if Core/NFS is down. Media, downloads, Immich photo trees, and similar libraries SHALL use the WSL host NFS mount of OMV `shared/` and `users/`, not a Docker NFS driver and not a Windows drive letter as `DATA_ROOT`.

#### Scenario: Same tree, host NFS transport
- **WHEN** Jellyfin on `mantle` mounts `shared/media`
- **THEN** that path is the household media tree from OMV via WSL NFS

### Requirement: BACKUP_DRIVE separate
The 4TB USB Restic REST target SHALL remain a variable distinct from `DATA_ROOT`, visible to WSL as a mount such as `/mnt/d`, not under `shared/media`.

#### Scenario: Restic REST on USB
- **WHEN** Restic REST is applied on `mantle`
- **THEN** its repository path uses `BACKUP_DRIVE`, not `shared/media`

### Requirement: Prep before OpenCloud, layout after spaces
Thin `data-root-prep` SHALL create `${DATA_ROOT}/system`, empty `users/`, and PUID-owned OpenCloud host dirs before phase A. It MUST NOT create household `users/<name>` homes or protected layout dirs under `shared/` (`media`, `downloads`, and similar). Full layout SHALL run only after OpenCloud space roots exist (created on an empty disk, or already present on a remounted disk).

#### Scenario: Prep does not mkdir shared/media
- **WHEN** `data-root-prep.sh` runs on an empty `DATA_ROOT`
- **THEN** `system/` and `users/` exist and `shared/media` has not been created by that script

### Requirement: Empty-disk OpenCloud order
On an empty data disk, after phase A the operator SHALL: log in so OpenCloud creates `users/<user>/files` with space xattrs; create Project Space `shared`; publish; create `photos-<user>` spaces as documented; then run `data-root-layout.sh`; then NFS/SMB. `core.sh` MUST NOT run layout or NFS.

#### Scenario: Layout after publish
- **WHEN** Space `shared` has been published onto `shared/files`
- **THEN** `data-root-layout.sh` may create protected dirs under `shared/` and apply ACL/sticky

### Requirement: Existing-disk OpenCloud does not recreate spaces
When `DATA_ROOT` already has OpenCloud posix/users/shared with `user.oc.space.*` xattrs, phase A SHALL reuse them. The operator MUST NOT be required to create Space `shared` again. Park/adopt scripts MAY be used only if `system/opencloud/{config,data}` is corrupt; posix/users/shared MUST NOT be wiped as the happy path.

#### Scenario: xattrs present after remount
- **WHEN** `getfattr` shows `user.oc.space.*` on `users/<user>/files` and `system/opencloud/projects/shared` after remount and phase A
- **THEN** the documented happy path is verify + layout + NFS, not create-space
