## Why

Nextcloud is on the HTPC for RAM and CPU, but the stack still used SQLite in the local `/config` volume and shipped no database. Household desktop/mobile sync needs PostgreSQL. The installer failed when pointed at the HTPC LAN IP because nothing listens on `:5432` there.

## What Changes

- Add a PostgreSQL sidecar to both Nextcloud compose files, on the stack network only.
- Keep Postgres data on a local Docker volume (not NFS), same as `/config`.
- Do **not** publish host port 5432. The wizard host is the Compose service name `postgres`.
- Add Komodo secret `NEXTCLOUD_DB_PASSWORD` (bootstrap + `VARIABLES.md` + periphery stack env).
- Document first-run: wipe a failed installer config volume, then install against `postgres`.

## Capabilities

### New Capabilities

- `nextcloud-db`: Nextcloud on periphery uses PostgreSQL in-stack; database volume is local; `5432` is not on the LAN.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs yet)

## Impact

- `stacks/workload/nextcloud/compose.yaml` and `compose.nfs.yaml`
- `stacks/komodo/stacks-periphery.toml`, `stacks/komodo/VARIABLES.md`
- `bootstrap/core.sh` (prompt + `[secrets]`), `bootstrap/nextcloud.md`
- Runtime: new `nextcloud-db` container on the HTPC; operators add `NEXTCLOUD_DB_PASSWORD` in Komodo if Core was already bootstrapped
- Out of scope: Windows PostgreSQL, publishing `:5432`, SQLite→Postgres `occ db:convert-type` for an already-working instance
