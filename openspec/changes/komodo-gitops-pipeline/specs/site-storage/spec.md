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
Jellyfin, Arr, qBittorrent, and Nextcloud SHALL mount subdirectories of this tree using `${DATA_ROOT}/...` (or the HTPC host’s equivalent `DATA_ROOT`). Shared household content uses `shared/`; per-user Nextcloud files and Memories use `users/<user>/files` and `users/<user>/photos`.

#### Scenario: Media and photos mounts
- **WHEN** Jellyfin and Nextcloud stacks are deployed
- **THEN** Jellyfin uses `${DATA_ROOT}/shared/media` and Nextcloud can access both `${DATA_ROOT}/shared/{files,photos}` and `${DATA_ROOT}/users/<user>/{files,photos}`

### Requirement: Host-specific roots only
The absolute `DATA_ROOT` path SHALL be a Komodo variable per server. On `nas` it SHALL be the OMV uuid mount (e.g. under `/srv/dev-disk-by-uuid-*`). On `htpc` it SHALL be the Docker Desktop-visible mount of the same OMV exports. The 4TB USB backup target SHALL be a separate HTPC variable (`BACKUP_DRIVE`) and MUST NOT be required to live under `DATA_ROOT`.

#### Scenario: Disk swap
- **WHEN** the OMV data disk UUID path changes
- **THEN** updating `DATA_ROOT` in Komodo is sufficient for stacks to use the new disk without editing committed compose files

#### Scenario: Restic REST storage
- **WHEN** Restic REST runs on `htpc`
- **THEN** its repository path uses `BACKUP_DRIVE` (the USB volume), not `shared/media`

### Requirement: Permission boundaries
NAS-only app state SHALL live under `${DATA_ROOT}/system/core`. HTPC app state SHALL live under `${DATA_ROOT}/system/periphery`. Household content SHALL live under `shared/` and `users/`. The HTPC SMB identity MAY have read/write on `shared/`, `users/`, and `system/periphery`, and MUST NOT have access to `system/core`.

#### Scenario: HTPC share ACL
- **WHEN** the HTPC Docker engine binds `DATA_ROOT` over SMB
- **THEN** it can persist Nextcloud, Jellyfin, Arr, qBittorrent, and Home Assistant config under `system/periphery` and write household data under `shared/` and `users/`, without reading Authelia, Vaultwarden, Pi-hole, or WireGuard data under `system/core`
