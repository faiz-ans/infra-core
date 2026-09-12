## ADDED Requirements

### Requirement: OpenCloud on Core with PosixFS
OpenCloud SHALL deploy on server `core`, attach to the `edge` Docker network, and SHALL NOT publish a host port. Caddy SHALL proxy `cloud.{$DOMAIN}` (and `oc.` / `opencloud.` aliases) to the OpenCloud service by container name on port 9200. Storage SHALL use the PosixFS driver with collaborative watch enabled. Config and OpenCloud-internal state SHALL live under `${DATA_ROOT}/system/opencloud`. Personal spaces SHALL map to `${DATA_ROOT}/users/<username>/files`. Each household user SHALL have a Project Space named `photos-<username>` bind-mounted to `${DATA_ROOT}/users/<username>/photos`. The household documents tree SHALL be one Project Space named `shared` at `/posix/projects/shared`, bind-mounted to `${DATA_ROOT}/shared/files`. `${DATA_ROOT}/shared/{media,games,photos,downloads,cameras}` SHALL NOT be OpenCloud spaces (SMB/NFS + HTPC apps only). The stack MUST NOT add nested Docker mounts of `files/` or `photos/` under the PosixFS root (host bind-mounts of space leaves onto those paths are required). Immich MAY continue to index `shared/photos` and `users/<user>/photos` over NFS. The container MUST run as `${PUID}:${PGID}`. The stack MUST NOT use DecomposedFS or store personal files only as opaque blobs.

#### Scenario: Caddy reaches OpenCloud on edge
- **WHEN** a client opens `https://cloud.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to OpenCloud on the edge network and does not proxy to an HTPC published port

#### Scenario: Personal space is files/
- **WHEN** OpenCloud user `alice` is created and PosixFS is in use
- **THEN** that user's personal space root is `${DATA_ROOT}/users/alice/files`

#### Scenario: Household shared is documents only
- **WHEN** an admin creates a Project Space named `shared` with PosixFS general path template `projects/{{.SpaceName}}` and parent bind `${DATA_ROOT}/system/opencloud/projects` → `/posix/projects`
- **THEN** that Space's files live at `${DATA_ROOT}/system/opencloud/projects/shared` and SHALL be bind-mounted to `${DATA_ROOT}/shared/files` for SMB/NFS

### Requirement: Phone ingest into photos
OpenCloud SHALL be the phone camera ingest path. First-run documentation SHALL instruct operators to set mobile automatic picture and video upload destination to the Project Space named `photos-<username>` (the space root, not Personal and not a default `CameraUpload` path). Caddy MUST NOT apply Authelia forward-auth to the whole OpenCloud hostname (DAV/TUS clients).

#### Scenario: Auto-upload lands on disk
- **WHEN** a household phone completes OpenCloud automatic photo upload to space `photos-<user>`
- **THEN** the files exist under `${DATA_ROOT}/users/<user>/photos` and are visible over SMB

### Requirement: Nextcloud removed from Core GitOps
The catalog MUST NOT deploy a Nextcloud stack. Caddy hostnames `nextcloud.` and `nc.` SHALL redirect to `cloud.{$DOMAIN}`. Bootstrap and `VARIABLES.md` MUST NOT require `NEXTCLOUD_*` secrets for new installs.

#### Scenario: Old Nextcloud hostname
- **WHEN** a client opens `https://nextcloud.{$DOMAIN}`
- **THEN** Caddy redirects to `https://cloud.{$DOMAIN}`
