## ADDED Requirements

### Requirement: Thin DATA_ROOT prep before phase A

NAS/Core bootstrap SHALL create `${DATA_ROOT}/system` and an empty `${DATA_ROOT}/users` parent (plus OpenCloud host directories under `system/opencloud`) via the prep script before phase-A OpenCloud Deploy. It MUST NOT require creating household `users/<name>` trees or the full `shared/` protected layout before OpenCloud space roots exist. Full household layout and NFS/SMB export of `shared/` and `users/` SHALL occur after OpenCloud publish (phase-B readiness), per bootstrap-phases.

#### Scenario: Bootstrap stops short of household layout

- **WHEN** Core bootstrap prep completes on a greenfield data disk
- **THEN** `system/` and empty `users/` exist and household media layout under `shared/` has not yet been mandated by prep
