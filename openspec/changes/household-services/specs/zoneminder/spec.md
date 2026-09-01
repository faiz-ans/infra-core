## ADDED Requirements

### Requirement: ZoneMinder on periphery
ZoneMinder SHALL deploy on `periphery` via ResourceSync using `ghcr.io/zoneminder-containers/zoneminder-base`. MariaDB, ZoneMinder `/config`, and `/log` SHALL be local Docker volumes on the HTPC and MUST NOT use the Docker NFS driver. The stack SHALL publish host port 8084 mapped to container port 80. Caddy SHALL proxy `cams.{$DOMAIN}`, `zm.{$DOMAIN}`, and `zoneminder.{$DOMAIN}` to `{$HTPC_UPSTREAM}:8084`. Database passwords SHALL come from Komodo `ZM_DB_PASSWORD`. Caddy MUST NOT apply Authelia forward-auth to these hostnames.

#### Scenario: UI through Caddy
- **WHEN** a client opens `https://cams.{$DOMAIN}`
- **THEN** Caddy on Core proxies to ZoneMinder’s published port on `HTPC_UPSTREAM`

#### Scenario: Database stays local
- **WHEN** ZoneMinder is deployed
- **THEN** the MariaDB data volume is on the HTPC engine and is not an NFS volume of `shared/` or `users/`

### Requirement: Event recordings on shared/cameras
ZoneMinder `/data` SHALL be the household camera tree. Catalog `compose.yaml` SHALL bind `${DATA_ROOT}/shared/cameras`. Catalog `compose.nfs.yaml` SHALL use Docker NFS of `${NFS_EXPORT}/cameras`. ResourceSync on this site SHALL list exactly one of those files (`compose.nfs.yaml`). Bootstrap SHALL create `shared/cameras` with the same permission contract as other `shared/` trees. The catalog MUST NOT store event recordings under `${DATA_ROOT}/system/`.

#### Scenario: NFS events mount
- **WHEN** the ZoneMinder NFS compose is deployed
- **THEN** captured events are written under the OMV `shared` export at `cameras/` and are visible over SMB as `shared/cameras`
