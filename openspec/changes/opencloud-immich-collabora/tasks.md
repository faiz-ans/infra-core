## 1. OpenCloud on Core

- [x] 1.1 Add `stacks/workload/opencloud/` compose (edge, PosixFS, PUID, collaboration env, extra_hosts) and `csp.yaml`
- [x] 1.2 Register the `opencloud` stack in `stacks-core.toml`
- [x] 1.3 Create `system/opencloud` in bootstrap tree + `data-root-perms.sh`; grant PUID write on `users/<user>`

## 2. Immich and Collabora on periphery

- [x] 2.1 Add Immich `compose.yaml` and `compose.nfs.yaml` (local DB/ML/upload; photo binds)
- [x] 2.2 Add Collabora compose (9980, ssl termination, aliasgroup1)
- [x] 2.3 Register `immich` and `collabora` in `stacks-periphery.toml`; remove `nextcloud`

## 3. Edge, Homepage, secrets

- [x] 3.1 Update Caddyfile: OpenCloud on edge, Immich/Collabora on HTPC, redirect old Nextcloud hosts
- [x] 3.2 Replace Homepage Nextcloud tile with OpenCloud and Immich
- [x] 3.3 Replace `NEXTCLOUD_*` with `OPENCLOUD_ADMIN_PASSWORD` and `IMMICH_DB_PASSWORD` in `VARIABLES.md` and `core.sh`

## 4. Remove Nextcloud and document first-run

- [x] 4.1 Delete `stacks/workload/nextcloud/` and `bootstrap/nextcloud.md`
- [x] 4.2 Add `bootstrap/opencloud.md` and `bootstrap/immich.md`; update README, `periphery.md`, `omv-nfs.md`
