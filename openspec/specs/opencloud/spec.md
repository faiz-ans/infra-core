## Purpose

TBD

## Requirements

### Requirement: OpenCloud on Core with PosixFS
OpenCloud SHALL deploy on server `core`, attach to the `edge` Docker network, and SHALL NOT publish a host port. Caddy SHALL proxy `cloud.{$DOMAIN}` (and `oc.` / `opencloud.` aliases) to the OpenCloud service by container name on port 9200. Storage SHALL use the PosixFS driver with collaborative watch enabled. Config and OpenCloud-internal state SHALL live under `${DATA_ROOT}/system/opencloud`. Personal spaces SHALL map to `${DATA_ROOT}/users/<username>/files`. Each household user SHALL have a Project Space named `photos-<username>` whose only member is that user (Can manage), bind-mounted to `${DATA_ROOT}/users/<username>/photos`. An instance admin MUST NOT remain a member of another user's photos space after create. Admins MAY still list those spaces in Settings → Spaces without file access. The household documents tree SHALL be one Project Space named `shared` at `/posix/projects/shared`, bind-mounted to `${DATA_ROOT}/shared/files`. `${DATA_ROOT}/shared/{media,games,photos,downloads,cameras}` SHALL NOT be OpenCloud spaces (SMB/NFS + HTPC apps only). The stack MUST NOT add nested Docker mounts of `files/` or `photos/` under the PosixFS root (host bind-mounts of space leaves onto those paths are required). Immich MAY continue to index `shared/photos` and `users/<user>/photos` over NFS. The container MUST run as `${PUID}:${PGID}`. The stack MUST NOT use DecomposedFS or store personal files only as opaque blobs.

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

### Requirement: Ordered OpenCloud first-run

The catalog SHALL document a single ordered first-run for OpenCloud on Core: secrets and `data-root-perms`, Deploy opencloud (+ collabora on periphery, Redeploy caddy if needed), adopt personal homes (`opencloud-adopt-homes.sh`), create Project Space named exactly `shared` then `opencloud-adopt-shared.sh` publish (inode bind) and restore, then `data-root-perms.sh` again for ACLs and sticky layout dirs. The happy path MUST appear before any failure appendix.

#### Scenario: New site with pre-created shared and homes

- **WHEN** `core.sh` / `data-root-perms.sh` has created `${DATA_ROOT}/shared` layout and `users/<household>` trees
- **THEN** the operator parks those trees, signs in so OpenCloud creates space xattrs, publishes the shared bind by inode equality, restores content, and re-runs `data-root-perms.sh`

### Requirement: OpenCloud readiness check

The catalog SHALL provide `bootstrap/opencloud-check.sh` that reports pass/fail (non-zero exit if any required check fails) for: opencloud and radicale containers Up; Collabora stack healthy when present; `user.oc.space.id` on household homes and on `projects/shared`; `${DATA_ROOT}/shared` same device:inode as `projects/shared`; sticky bit on `${DATA_ROOT}/shared`; root ownership of protected layout sample paths; Radicale data dir owned by `${PUID}`; and that OpenCloud env includes `COLLABORATION_APP_PROOF_DISABLE=true` when the collaboration service is enabled.

#### Scenario: Shared publish not bound

- **WHEN** `projects/shared` has a space id but `shared/` is a different inode
- **THEN** the check fails and points the operator at `opencloud-adopt-shared.sh publish`

### Requirement: Greenfield-first OpenCloud documentation

OpenCloud first-run documentation SHALL present the greenfield order (prep, phase-A deploy, login-created homes, Space `shared`, publish bind, layout perms, then phase-full stacks) as the default happy path. Park/restore adopt scripts SHALL be documented as utilities for sites that already have homes or `shared/` content. The readiness check SHALL remain the verification step after layout.

#### Scenario: Doc order for empty site

- **WHEN** an operator follows `bootstrap/opencloud.md` on a disk without pre-created space roots
- **THEN** the primary steps do not require park before first login or before creating Space `shared`
