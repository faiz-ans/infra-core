## ADDED Requirements

### Requirement: Native mounts replace OpenMediaVault
SET SHALL mount each storage volume by UUID once (internal volumes stay at `/`; others at `/mnt/site/<id>`, where id is the partition id or the disk id when the disk has no partitions) using OS-native tooling (systemd mount or equivalent). The three data roots SHALL be sibling directories on that disk mount and bind-mounted to `site.data.roots.*`. SET MUST NOT mount the same UUID at `/appdata`, `/groups`, and `/users`. The catalog MUST NOT install or configure OpenMediaVault. When `operations.host.manager` is Cockpit, Cockpit SHALL remain able to show those mounts.

#### Scenario: No OMV package
- **WHEN** SET completes on a storage host
- **THEN** `openmediavault` is not installed and the owned roots are mounted and visible with `findmnt`

#### Scenario: Roots are siblings under one disk mount
- **WHEN** a non-internal disk owns `appdata`, `groups`, and `users`
- **THEN** that UUID is mounted once and `/appdata`, `/groups`, and `/users` are bind mounts of sibling directories on that disk

### Requirement: Host-local roots are owned by a disk
A host MAY declare `data.roots` as any name mapped to an absolute path (not limited to `appdata`, `groups`, or `users`). When a disk has `partitions`, a partition owns those names via `partitions[].roots` and is what `roles.storage.drives[].id` references. When a disk has no partitions, the disk itself owns them via `roots` and is what a storage drive references. SET SHALL create each host root on that volume (internal: mkdir the declared path; otherwise sibling dirs on the volume mount, bind-mounted to the declared paths). Pods SHALL resolve `${host.data.roots.<name>}` from `hosts[].data.roots` only. Every host root, including one that shares a site directory, MUST be listed on its disk or partition. When that volume is a storage drive and the host-root path equals a site root that drive already mounts, SET SHALL share that directory and SHALL NOT create a second directory or bind. The host-root name is not what selects the share. Any other host root MUST NOT be owned by a volume that is a storage drive. SET SHALL error if a host root is unowned, owned twice, or listed on a storage drive with a different path.

#### Scenario: Workload disk owns a local appdata path
- **WHEN** a host sets `data.roots.appdata: /var/lib/site-appdata` and a non-storage disk (or its partition) lists `roots: [appdata]`
- **THEN** SET creates that path on that volume and `${host.data.roots.appdata}` resolves to `/var/lib/site-appdata`

#### Scenario: Storage drive cannot own host roots
- **WHEN** a partition or disk id is listed in any host’s `roles.storage.drives` and that same volume also has `roots` whose path is not the site root that drive already mounts
- **THEN** SET fails with an error and does not apply

#### Scenario: Host appdata shares the site appdata path
- **WHEN** the storage host sets `data.roots.appdata` to the same path as `site.data.roots.appdata`, its storage drive already mounts that root, and that volume's `roots` list includes `appdata`
- **THEN** validation passes, SET keeps the one site bind, and `${host.data.roots.appdata}` resolves to that path

#### Scenario: A matching path without a roots list is unowned
- **WHEN** the storage host sets `data.roots.appdata` to the site appdata path and no disk or partition lists `appdata`
- **THEN** SET fails because the host root is not owned

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
Disk `import` is a typed list. `from:` is a path relative to that disk’s systemd mount. Root types (`appdata-root`, `groups-root`, `users-root`) merge into the matching `site.data.roots` path. Home types (`appdata-home`, `group-home`, `user-home`) land under that root as a home; `as:` (or `to:`) relocates the home under the root and creates the path if needed; an existing dest is merged. SET SHALL run on root-owning hosts first. When the source disk is not on the dest-root owner, SET SHALL export that dest root over NFS (same inference as an off-host service root), import, then drop the share unless a placed service still needs it. A successful import MUST be stamped so a later SET does not copy again. Imports of files the product now generates (Caddyfile, Authelia configuration) SHALL be written with a `.old` suffix beside the live generated file. The operator removes the `import` block after success.

#### Scenario: Remap shared to groups/all
- **WHEN** desired imports `type: group-home` `from: /shared` `as: /all`
- **THEN** after a successful SET the content exists under the groups root’s `all` directory and a second SET does not duplicate it

#### Scenario: Appdata homes stay under appdata
- **WHEN** desired imports `type: appdata-home` `from: /system/caddy` from a disk that also has `/users`
- **THEN** the dest is the appdata root plus `caddy` and `/users/caddy` is not a valid dest

### Requirement: Service-specific dirs only when needed
SET SHALL create service-specific directories (for example downloads or cameras) only when an official service that uses them is in desired. A storage host with no such service MUST NOT receive the old full `shared/{media,games,…}` layout.

#### Scenario: No qBit means no downloads dir
- **WHEN** desired has no qBittorrent instance
- **THEN** SET does not create a downloads directory under groups
