## ADDED Requirements

### Requirement: Nextcloud uses in-stack PostgreSQL
The Nextcloud stack on `periphery` SHALL include a PostgreSQL service on the same Compose network. Nextcloud SHALL reach it by the Compose service name `postgres` on port 5432. The database service MUST NOT publish port 5432 on the HTPC host.

#### Scenario: Wizard host is Compose DNS
- **WHEN** an operator completes the Nextcloud installer against this stack
- **THEN** the database host is `postgres` (not `HTPC_UPSTREAM` or a LAN IP) and the connection succeeds without a host firewall rule for 5432

#### Scenario: Port is not on the LAN
- **WHEN** a LAN client connects to `HTPC_UPSTREAM` on TCP 5432
- **THEN** nothing from this stack accepts that connection

### Requirement: PostgreSQL data is local
PostgreSQL data SHALL live on a local Docker volume on the HTPC. That volume MUST NOT use the Docker NFS driver or a path under `DATA_ROOT` / OMV exports.

#### Scenario: Config and database survive NFS down
- **WHEN** Core or NFS is unreachable
- **THEN** the Nextcloud `/config` volume and the PostgreSQL data volume remain on the HTPC engine

### Requirement: Database password is a Komodo secret
The PostgreSQL password SHALL come from Komodo key `NEXTCLOUD_DB_PASSWORD` (secret). The catalog MUST NOT contain a live password. Bootstrap SHALL prompt for the key on new Core installs and write it to Core `[secrets]`.

#### Scenario: Stack interpolates the secret
- **WHEN** ResourceSync deploys the Nextcloud stack
- **THEN** the Postgres service receives `POSTGRES_PASSWORD` from `[[NEXTCLOUD_DB_PASSWORD]]`
