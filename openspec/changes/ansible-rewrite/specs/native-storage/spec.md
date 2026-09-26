## ADDED Requirements

### Requirement: Native mounts replace OpenMediaVault
SET SHALL mount storage disks by UUID using OS-native tooling (systemd mount or equivalent). The catalog MUST NOT install or configure OpenMediaVault. When `operations.host.manager` is Cockpit, Cockpit SHALL remain able to show those mounts.

#### Scenario: No OMV package
- **WHEN** SET completes on a storage host
- **THEN** `openmediavault` is not installed and the owned roots are mounted and visible with `findmnt`

### Requirement: SMB for people, inferred NFS for apps
`data.access.filesystem: smb` SHALL export user-homes and group-homes over Samba to site users. SET SHALL create an NFS export only when a placed service references a root owned on another host, granted to that consumer host IP as the workload user UID. Same-host references SHALL use a local path.

#### Scenario: Immich on another host needs users
- **WHEN** Immich on host B references `${site.data.roots.users}` owned on host A
- **THEN** SET exports that path from A to B’s IP and mounts it on B as the workload UID

#### Scenario: OpenCloud on the owner host
- **WHEN** OpenCloud runs on the host that owns `users`
- **THEN** SET does not create an NFS export for that reference

### Requirement: No home data deletion
SET MUST NOT delete user-home or group-home directory trees when accounts are removed or services change. Creating and moving roots is allowed; wiping household files is not.

#### Scenario: User removed from desired
- **WHEN** a site user is deleted from desired and Day 2 SET runs
- **THEN** the account is gone from unix/LDAP/SSO and that user’s home directory still exists on disk

### Requirement: Import is stamped and generated files get .old
Disk `import` blocks SHALL copy or merge named old trees onto new roots or homes and report success or failure in observed. A successful import MUST be stamped so a later SET does not copy again. Imports of files the product now generates (Caddyfile, Authelia configuration) SHALL be written with a `.old` suffix beside the live generated file. The operator removes the `import` block after success.

#### Scenario: Remap shared to groups/all
- **WHEN** desired imports `from: /shared` `to: /all` under the groups root
- **THEN** after a successful SET the content exists under the groups root’s `all` directory and a second SET does not duplicate it

### Requirement: Service-specific dirs only when needed
SET SHALL create service-specific directories (for example downloads or cameras) only when an official service that uses them is in desired. A storage host with no such service MUST NOT receive the old full `shared/{media,games,…}` layout.

#### Scenario: No qBit means no downloads dir
- **WHEN** desired has no qBittorrent instance
- **THEN** SET does not create a downloads directory under groups
