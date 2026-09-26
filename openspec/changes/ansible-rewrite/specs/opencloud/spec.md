## MODIFIED Requirements

### Requirement: OpenCloud on Core with PosixFS
When desired lists OpenCloud on a workload host, SET SHALL deploy OpenCloud with PosixFS. Config and internal state SHALL live under the `appdata` root (`appdata/opencloud`). Personal spaces SHALL map to `users/<username>/files`. Photos spaces SHALL map to `users/<username>/photos`. The household documents space SHALL bind to `groups/all` (or `groups/all/files` if a documents leaf is required). `groups/all/{media,downloads,cameras}` and similar SHALL NOT be OpenCloud spaces. Caddy SHALL proxy the official OpenCloud subdomains to that instance. The container MUST run as the workload user’s uid/gid. SET MUST NOT recreate spaces when `user.oc.space.*` xattrs already exist.

#### Scenario: Personal space is files/
- **WHEN** OpenCloud user `alice` exists and PosixFS is in use
- **THEN** that user's personal space root is under the users root at `alice/files`

#### Scenario: Household shared is groups/all
- **WHEN** the documents space is published
- **THEN** its files are reachable at the groups root `all` tree for SMB

### Requirement: Phone ingest into photos
OpenCloud SHALL remain the phone camera ingest path to `photos-<username>`. Caddy MUST NOT apply Authelia forward-auth to the whole OpenCloud hostname (DAV/TUS). SSO SHALL be OIDC as encoded in the official pack.

#### Scenario: Auto-upload lands on disk
- **WHEN** a phone completes OpenCloud automatic photo upload to space `photos-<user>`
- **THEN** the files exist under that user’s `photos` directory and are visible over SMB

### Requirement: Nextcloud removed from Core GitOps
The catalog MUST NOT deploy Nextcloud. If Caddy is generated, `nextcloud.` and `nc.` MAY redirect to the OpenCloud hostname.

#### Scenario: Old Nextcloud hostname
- **WHEN** a client opens the Nextcloud alias and OpenCloud is placed
- **THEN** Caddy redirects to the OpenCloud primary hostname

## REMOVED Requirements

### Requirement: Ordered OpenCloud first-run
**Reason**: Shell adopt scripts are archived; SET + official pack perform binds and refuse space recreate when xattrs exist.
**Migration**: catalog-templates OpenCloud lessons + import `.old` for generated config.

### Requirement: OpenCloud readiness check
**Reason**: `opencloud-check.sh` is archived; GET B / SET reports replace it.
**Migration**: Observed mounts, xattrs, and container list.

### Requirement: Greenfield-first OpenCloud documentation
**Reason**: First-run novels are archived.
**Migration**: Product README Day 0/1/2 plus official pack comments.
