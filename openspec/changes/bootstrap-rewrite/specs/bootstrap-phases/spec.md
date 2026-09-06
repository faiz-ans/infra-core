## ADDED Requirements

### Requirement: Greenfield bootstrap order

New-site bootstrap SHALL follow: (0) topology definition and TOML generation; server/Docker/Komodo install and site vars; (1) `data-root-prep` creating `system/`, empty `users/`, and PUID-owned OpenCloud host dirs; (2) Authelia `users.yml` for that site; (3) ResourceSync apply of `stacks-bootstrap.toml` only (Authelia, Caddy, Pi-hole as assigned, Homepage, OpenCloud, Collabora/Radicale as assigned); (4) household users log in so OpenCloud creates `users/<user>` with space xattrs; (5) an admin creates Project Space named exactly `shared`; (6) publish empty `${DATA_ROOT}/shared` bind to `projects/shared` + fstab; (7) `data-root-layout` creates protected dirs and applies ACL/sticky; (8) OMV SMB/NFS for `shared` and `users`; (9) ResourceSync apply of phase-full TOMLs. Adopt park/restore scripts SHALL remain available for non-greenfield recovery.

#### Scenario: Empty disk greenfield

- **WHEN** a site has no pre-created `users/<name>` homes and no content under `${DATA_ROOT}/shared` before publish
- **THEN** the operator completes spaces and publish without running park, then runs layout perms before deploying phase-full media stacks

### Requirement: Split host permission scripts

The catalog SHALL provide separate `data-root-prep` and `data-root-layout` scripts (not a single gated mode flag). Prep MUST NOT create household `users/<name>` homes or protected layout dirs under `shared/`. Layout MUST create protected directories under the published `shared/` bind and under existing OpenCloud homes (`files`, `photos`, and the shared layout set), apply ACL/sticky, and retain this reference site’s configured defaults (`DATA_ROOT`, household names, admin, groups) rather than blanking them.

#### Scenario: Prep before OpenCloud Deploy

- **WHEN** prep has been run and OpenCloud is Deployed
- **THEN** `users/` exists as an empty writable parent and `system/opencloud/{posix,projects,radicale}` are owned by `${PUID}:${PGID}` without pre-creating `users/faiz` or `shared/media`

### Requirement: Homepage rollout seed

The catalog SHALL ship a minimal Homepage config seed (links suitable for phase A: Komodo, OMV, Authelia, Pi-hole, OpenCloud) for new sites. The reference site’s existing `stacks/platform/homepage/config/*` MUST NOT be replaced by that seed.

#### Scenario: New site copies seed

- **WHEN** a new site initializes Homepage config from the seed
- **THEN** phase-A Homepage shows the bootstrap link set, and this repository’s customized Homepage config files remain unchanged
