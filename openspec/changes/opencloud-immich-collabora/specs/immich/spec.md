## ADDED Requirements

### Requirement: Immich on periphery with local app state
Immich SHALL deploy on `periphery` via ResourceSync. PostgreSQL, Redis/Valkey, machine-learning cache, and Immich upload/thumbnail storage SHALL be local Docker volumes on the HTPC. Those volumes MUST NOT use the Docker NFS driver. The stack SHALL publish port 2283 for Caddy. Caddy SHALL proxy `photos.{$DOMAIN}` (and `immich.` alias) to `{$HTPC_UPSTREAM}:2283`.

#### Scenario: Gallery through Caddy
- **WHEN** a client opens `https://photos.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to Immich’s published port on `HTPC_UPSTREAM`

#### Scenario: Database stays local
- **WHEN** Immich is deployed
- **THEN** the Postgres data volume is on the HTPC engine and is not an NFS volume of `shared/` or `users/`

### Requirement: External Libraries on the photo trees
Immich SHALL mount household photo trees at container paths suitable for External Libraries: `shared/photos` and `users/` (so `users/<user>/photos` is reachable). Catalog `compose.yaml` SHALL bind `${DATA_ROOT}/...`. Catalog `compose.nfs.yaml` SHALL use Docker NFS of `${NFS_EXPORT}/photos` and `${NFS_USERS}`. ResourceSync SHALL list exactly one of those files. First-run documentation SHALL tell operators to add External Libraries for those paths and MUST NOT tell them to use Immich mobile backup as the NAS camera ingest.

#### Scenario: NFS photos mount
- **WHEN** the Immich NFS compose is deployed
- **THEN** Immich can read `${NFS_EXPORT}/photos` and the `users` export for External Library import paths
