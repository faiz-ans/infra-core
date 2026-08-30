## Context

linuxserver Nextcloud on `periphery` keeps `/config` on a local volume and household files on NFS. The catalog implied SQLite in that volume and did not run a database. The official installer offers PostgreSQL, but operators who typed the HTPC LAN IP (`HTPC_UPSTREAM:5432`) got connection refused: this site never published Postgres on the Windows host.

## Goals / Non-Goals

**Goals:**

- Nextcloud talks to PostgreSQL on the Compose network.
- Database files stay on a local HTPC volume (not NFS).
- Password is a Komodo secret, not in git.
- First-run docs use host `postgres`, not a LAN IP.

**Non-Goals:**

- Publishing `5432` on Windows or opening it in the firewall.
- Installing PostgreSQL on Windows.
- Migrating an already-working SQLite `config.php` with `occ db:convert-type`.
- Switching away from the linuxserver Nextcloud image.

## Decisions

### 1. Sidecar in the Nextcloud stack, service name `postgres`

Nextcloud reaches `postgres:5432` by Compose DNS. `container_name` is `nextcloud-db` so `docker ps` is unambiguous. Official `postgres:16-alpine`. `POSTGRES_DB` / `POSTGRES_USER` are literals `nextcloud`. Password is `${NEXTCLOUD_DB_PASSWORD}`.

**Alternative considered:** Windows Postgres on `HTPC_UPSTREAM:5432`. Rejected: WSL2 hairpin, `listen_addresses`, and a LAN listener this catalog does not want.

**Alternative considered:** Official Nextcloud image + env auto-install. Rejected: larger cutover than a sidecar; linuxserver already owns `/config`, TLS-on-443, and `custom-cont-init.d`.

### 2. Local volume, no host port

Named volume `nextcloud-postgres` (same locality as `nextcloud-config`). No `ports:` on the database service. Nextcloud `depends_on` Postgres with `service_healthy` (`pg_isready`).

### 3. Secret `NEXTCLOUD_DB_PASSWORD`

Bootstrap prompts and writes `[secrets]`. Periphery stack env interpolates `[[NEXTCLOUD_DB_PASSWORD]]`. Sites that already ran `core.sh` add the key in the Komodo UI (do not re-run bootstrap just for this).

### 4. Web installer still creates the admin

linuxserver does not honor official `POSTGRES_*` / `NEXTCLOUD_ADMIN_*` auto-install. After deploy, the wizard uses PostgreSQL, host `postgres`, database/user `nextcloud`, password from that secret. A failed prior wizard requires deleting `nextcloud-config` only; wipe `nextcloud-postgres` only if the DB was created with the wrong password.

## Risks / Trade-offs

- **[linuxserver installer mangles DB credentials]** → Document exact wizard fields; if `config.php` is wrong, wipe `nextcloud-config` and retry.
- **[Existing Core has no secret]** → First-run doc: add `NEXTCLOUD_DB_PASSWORD` in Komodo before redeploy.
- **[Password change after first Postgres init]** → Official image bakes the role on first start; changing the secret later does not update the role. Recreate the volume only if the operator accepts a fresh database.

## Migration Plan

1. Add the secret in Komodo (or new bootstrap).
2. Sync the catalog; deploy `nextcloud`.
3. Wipe `nextcloud-config` if a previous wizard ran.
4. Install against `postgres`.
5. Rollback: remove the `postgres` service and volume from compose, redeploy, wipe `nextcloud-config`, install SQLite again.

## Open Questions

- None. First-run stays the linuxserver wizard (no `occ maintenance:install` script in this change).
