## MODIFIED Requirements

### Requirement: DATA_ROOT tree
Household data SHALL use three logical roots: `appdata` (service state), `groups` (including `all`), and `users` (per-person homes). SET SHALL NOT create `system/`, `shared/`, or host-named appdata folders (`appdata/core`) as the contract.

#### Scenario: Tree after SET
- **WHEN** a storage host owns all three roots
- **THEN** `appdata/`, `groups/`, and `users/` exist on the owning drive and `system/` is not required

### Requirement: Existing-disk OpenCloud does not recreate spaces
When a mounted users/groups tree already has OpenCloud `user.oc.space.*` xattrs, SET SHALL reuse them. The operator MUST NOT be required to create Space `shared` or `all` again. Homes MUST NOT be wiped as the happy path.

#### Scenario: xattrs present after remount
- **WHEN** `getfattr` shows `user.oc.space.*` on a user files tree after mount and SET
- **THEN** SET does not create a new space and does not delete that tree

## REMOVED Requirements

### Requirement: Workloads bind the tree via variables
**Reason**: Compose `${DATA_ROOT}` / OMV NFS variables are replaced by topology `${site.data.roots.*}` resolution.
**Migration**: catalog-templates + native-storage inferred NFS.

### Requirement: Host-specific roots only
**Reason**: OMV export names and `NAS_LAN_IP` are gone.
**Migration**: root ownership on storage drives; inferred NFS to consumer IPs.

### Requirement: Prep before OpenCloud, layout after spaces
**Reason**: `data-root-prep.sh` / `data-root-layout.sh` are archived; SET creates roots and service dirs as needed.
**Migration**: native-storage SET + OpenCloud official pack.

### Requirement: Empty-disk OpenCloud order
**Reason**: First-run shell order is replaced by SET + official OpenCloud steps.
**Migration**: opencloud + catalog-templates requirements.
