## Purpose

TBD

## Requirements

### Requirement: DATA_ROOT tree
Household data SHALL use three logical roots: `appdata` (service state), `groups` (including `all`), and `users` (per-person homes). SET SHALL NOT create `system/`, `shared/`, or host-named appdata folders (`appdata/core`) as the contract.

#### Scenario: Tree after SET
- **WHEN** a storage host owns all three roots
- **THEN** `appdata/`, `groups/`, and `users/` exist on the owning drive and `system/` is not required

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

### Requirement: Existing-disk OpenCloud does not recreate spaces
When a mounted users/groups tree already has OpenCloud `user.oc.space.*` xattrs, SET SHALL reuse them. The operator MUST NOT be required to create Space `shared` or `all` again. Homes MUST NOT be wiped as the happy path.

#### Scenario: xattrs present after remount
- **WHEN** `getfattr` shows `user.oc.space.*` on a user files tree after mount and SET
- **THEN** SET does not create a new space and does not delete that tree
