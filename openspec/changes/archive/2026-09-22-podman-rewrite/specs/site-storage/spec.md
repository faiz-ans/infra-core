## ADDED Requirements

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
