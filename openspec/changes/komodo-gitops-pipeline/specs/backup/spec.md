## ADDED Requirements

### Requirement: NAS is the restic client
A Restic client stack SHALL run on `nas` and SHALL back up `${DATA_ROOT}` including `system/vaultwarden` and the rest of the `DATA_ROOT` tree required for restore of NAS app state and household data. The restic repository SHALL be the Restic REST server on `htpc`. Repository password and REST credentials SHALL be Komodo secrets.

#### Scenario: Snapshot from nas
- **WHEN** the NAS restic job runs successfully
- **THEN** a snapshot exists on the HTPC REST repository and includes `${DATA_ROOT}/system/vaultwarden`

### Requirement: HTPC is the restic REST target
A Restic REST server SHALL run on `htpc` with repository storage on `${BACKUP_DRIVE}` (the 4TB USB volume). It MUST NOT store the repository under `${DATA_ROOT}/shared/media`. The REST listen port SHALL be published on the Windows LAN IP so the NAS client can reach `HTPC_UPSTREAM`.

#### Scenario: USB, not media share
- **WHEN** Restic REST is deployed
- **THEN** its data directory is on `BACKUP_DRIVE` and is distinct from OMV `shared/media`
