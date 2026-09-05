## ADDED Requirements

### Requirement: OpenCloud on Core with PosixFS
OpenCloud SHALL deploy on server `core`, attach to the `edge` Docker network, and SHALL NOT publish a host port. Caddy SHALL proxy `cloud.{$DOMAIN}` (and `oc.` / `opencloud.` aliases) to the OpenCloud service by container name on port 9200. Storage SHALL use the PosixFS driver with collaborative watch enabled. Config and OpenCloud-internal state SHALL live under `${DATA_ROOT}/system/opencloud`. Personal spaces SHALL map to `${DATA_ROOT}/users/<username>`. The household `${DATA_ROOT}/shared` tree SHALL be one Project Space whose on-disk path is `/posix/projects/shared` (Space name `shared`), via a single bind of the whole `shared/` directory. The stack MUST NOT bind `${DATA_ROOT}/shared/files` or `shared/photos` as nested mounts under the PosixFS root (nested Docker mounts break space xattrs and the filesystem watch). Immich MAY continue to index `shared/photos` over NFS. The container MUST run as `${PUID}:${PGID}`. The stack MUST NOT use DecomposedFS or store personal files only as opaque blobs.

#### Scenario: Caddy reaches OpenCloud on edge
- **WHEN** a client opens `https://cloud.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to OpenCloud on the edge network and does not proxy to an HTPC published port

#### Scenario: Personal space is the user home
- **WHEN** OpenCloud user `alice` is created and PosixFS is in use
- **THEN** that user's personal space files appear at `${DATA_ROOT}/users/alice` including `files/` and `photos/` as ordinary directories

#### Scenario: Household shared is a Project Space
- **WHEN** an admin creates a Project Space named `shared` with PosixFS general path template `projects/{{.SpaceName}}` and parent bind `${DATA_ROOT}/system/opencloud/projects` → `/posix/projects`
- **THEN** that Space's files live at `${DATA_ROOT}/system/opencloud/projects/shared` and SHALL be bind-mounted to `${DATA_ROOT}/shared` for SMB/NFS
### Requirement: Phone ingest into photos
OpenCloud SHALL be the phone camera ingest path. First-run documentation SHALL instruct operators to set mobile automatic picture and video upload destination to the personal-space `photos` folder (not a default `CameraUpload` path). Caddy MUST NOT apply Authelia forward-auth to the whole OpenCloud hostname (DAV/TUS clients).

#### Scenario: Auto-upload lands on disk
- **WHEN** a household phone completes OpenCloud automatic photo upload to Personal `photos`
- **THEN** the files exist under `${DATA_ROOT}/users/<user>/photos` and are visible over SMB

### Requirement: Nextcloud removed from Core GitOps
The catalog MUST NOT deploy a Nextcloud stack. Caddy hostnames `nextcloud.` and `nc.` SHALL redirect to `cloud.{$DOMAIN}`. Bootstrap and `VARIABLES.md` MUST NOT require `NEXTCLOUD_*` secrets for new installs.

#### Scenario: Old Nextcloud hostname
- **WHEN** a client opens `https://nextcloud.{$DOMAIN}`
- **THEN** Caddy redirects to `https://cloud.{$DOMAIN}`
