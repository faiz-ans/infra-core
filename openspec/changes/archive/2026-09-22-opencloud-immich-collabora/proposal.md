## Why

Nextcloud was the HTPC consumer of `shared/{files,photos}` and `users/<user>/{files,photos}`, including Memories as a gallery. That PHP stack is heavier than this site needs, fights External Storage over NFS, and is a poor fit for filesystem-canonical photos. File sync, phone ingest, office editing, and photo gallery should be separate apps that consume the existing `DATA_ROOT` tree.

## What Changes

- **BREAKING:** Remove the Nextcloud stack (compose, NFS variant, first-run doc, Komodo ResourceSync entry, secrets, Homepage tile, Caddy HTPC upstream on `:8080`).
- Add **OpenCloud** on `core` (edge network): PosixFS on local binds of `users/` and `shared/`, phone/desktop ingest, sharing. Personal space root is `users/<user>/`; household Project Space `shared` is `${DATA_ROOT}/shared`; camera auto-upload target is `photos/`.
- Add **Immich** on `periphery`: gallery only. External Libraries of `shared/photos` and `users/<user>/photos`. Postgres/Redis/ML/thumbnails on local HTPC volumes. Do not use Immich mobile backup as the NAS ingest path.
- Add **Collabora Online** on `periphery`: WOPI office editing for OpenCloud. Caddy hostname `office.{$DOMAIN}`.
- Caddy: `cloud.` → OpenCloud on edge; `photos.` → Immich; `office.` → Collabora. Redirect `nextcloud.` / `nc.` to `cloud.`.
- Bootstrap/Komodo: replace Nextcloud secrets with OpenCloud admin password and Immich DB password. Keep `NFS_USERS` for Immich.
- Authelia OIDC for OpenCloud/Immich is **out of scope** (edge gate is still off during site bring-up). Caddy MUST NOT put `authelia_gate` on OpenCloud DAV/TUS or Immich `/api`.

## Capabilities

### New Capabilities

- `opencloud`: OpenCloud on Core with PosixFS, public URL `cloud.{$DOMAIN}`, phone auto-upload into `users/<user>/photos`.
- `immich`: Immich on periphery with External Libraries on the photo trees; local DB/ML volumes.
- `collabora`: Collabora on periphery, WOPI through Caddy `office.{$DOMAIN}`, used by OpenCloud.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs yet)

## Impact

- Delete `stacks/workload/nextcloud/` and `bootstrap/nextcloud.md`.
- Add `stacks/workload/opencloud/`, `stacks/workload/immich/`, `stacks/workload/collabora/`.
- `stacks/komodo/stacks-core.toml`, `stacks-periphery.toml`, `VARIABLES.md`.
- `stacks/platform/caddy/Caddyfile`, Homepage `services.yaml`.
- `bootstrap/core.sh`, `data-root-perms.sh`, `periphery.md`, `README.md`, `omv-nfs.md`.
- Runtime: new Core container `opencloud`; new HTPC stacks `immich` and `collabora`; remove `nextcloud` / `nextcloud-db`.
