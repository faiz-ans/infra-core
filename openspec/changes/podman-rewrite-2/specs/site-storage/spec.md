## ADDED Requirements

### Requirement: Prep before OpenCloud, layout after spaces
Thin `data-root-prep` SHALL create `${DATA_ROOT}/system`, empty `users/`, and PUID-owned OpenCloud host dirs before phase A. It MUST NOT create household `users/<name>` homes or protected layout dirs under `shared/` (`media`, `downloads`, and similar). Full layout SHALL run only after OpenCloud space roots exist (created on an empty disk, or already present on a remounted disk).

#### Scenario: Prep does not mkdir shared/media
- **WHEN** `data-root-prep.sh` runs on an empty `DATA_ROOT`
- **THEN** `system/` and `users/` exist and `shared/media` has not been created by that script

### Requirement: Empty-disk OpenCloud order
On an empty data disk, after phase A the operator SHALL: log in so OpenCloud creates `users/<user>/files` with space xattrs; create Project Space `shared`; publish; create `photos-<user>` spaces as documented; then run `data-root-layout.sh`; then NFS/SMB. `core.sh` MUST NOT run layout or NFS.

#### Scenario: Layout after publish
- **WHEN** Space `shared` has been published onto `shared/files`
- **THEN** `data-root-layout.sh` may create protected dirs under `shared/` and apply ACL/sticky

### Requirement: Existing-disk OpenCloud does not recreate spaces
When `DATA_ROOT` already has OpenCloud posix/users/shared with `user.oc.space.*` xattrs, phase A SHALL reuse them. The operator MUST NOT be required to create Space `shared` again. Park/adopt scripts MAY be used only if `system/opencloud/{config,data}` is corrupt; posix/users/shared MUST NOT be wiped as the happy path.

#### Scenario: xattrs present after remount
- **WHEN** `getfattr` shows `user.oc.space.*` on `users/<user>/files` and `system/opencloud/projects/shared` after remount and phase A
- **THEN** the documented happy path is verify + layout + NFS, not create-space
