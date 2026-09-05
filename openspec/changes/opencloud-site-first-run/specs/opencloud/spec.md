## ADDED Requirements

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
