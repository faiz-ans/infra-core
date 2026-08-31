## Context

The catalog already treats `${DATA_ROOT}` as the source of truth (`shared/{files,photos}`, `users/<user>/{files,photos}`). Nextcloud on periphery consumed those trees over Docker NFS (External Storage + Memories). That placement put Posix-hostile NFS and a PHP stack on the HTPC write path for phone backups.

This change splits the jobs: OpenCloud writes files on Core local disk; Immich indexes photos on periphery; Collabora edits office documents on periphery CPU.

## Goals / Non-Goals

**Goals:**

- Filesystem-canonical trees stay readable over SMB and restic.
- Phone camera auto-upload lands in `users/<user>/photos` via OpenCloud.
- Immich External Libraries scan those photo trees; Immich does not own originals.
- Collabora is reachable at `office.{$DOMAIN}` for in-browser editing from OpenCloud.
- Nextcloud is gone from ResourceSync, Caddy, Homepage, and bootstrap.

**Non-Goals:**

- Authelia OIDC for OpenCloud/Immich (later, when the edge gate is turned on).
- Immich hardware transcoding / ML GPU.
- Generic Android folder auto-upload beyond pictures/videos (OpenCloud app limitation).
- Running OpenCloud or PosixFS on the HTPC over NFS.
- DecomposedFS / S3 blob layout.

## Decisions

### 1. OpenCloud on Core, PosixFS, local binds

OpenCloud joins the `edge` network (Caddy `opencloud:9200`). Config/state under `${DATA_ROOT}/system/opencloud`. PosixFS root is `/var/lib/opencloud/storage/users` with:

- `${DATA_ROOT}/users` → `.../users` (personal space `users/{{.User.Username}}` = `users/<user>/`)
- `${DATA_ROOT}/shared` → `.../projects` (project space named `files` or `photos` maps to `shared/files` or `shared/photos`)

`STORAGE_USERS_POSIX_WATCH_FS=true` so SMB/Finder writes are noticed. Container UID is `${PUID}:${PGID}`. `OC_INSECURE=true` and `PROXY_ENABLE_BASIC_AUTH=true` because Caddy uses internal TLS and mobile DAV is not OIDC yet.

**Alternative considered:** OpenCloud on periphery over existing NFS compose. Rejected: PosixFS needs xattrs; catalog NFS is `nfsvers=4` + `nolock` from Docker Desktop.

**Alternative considered:** DecomposedFS. Rejected: breaks SMB/restic human-readable trees.

### 2. Immich on periphery, External Libraries only

Official Immich compose (server, ML, Valkey, vector Postgres). Postgres, Redis, ML cache, and Immich `UPLOAD_LOCATION` are **local** named volumes. Photo originals are extra binds (`compose.yaml`: `${DATA_ROOT}/shared/photos` and `${DATA_ROOT}/users`; `compose.nfs.yaml`: Docker NFS of those exports). First-run: add External Libraries at `/mnt/photos` and `/mnt/users/<user>/photos`. Do not enable Immich mobile backup.

Site ResourceSync uses `compose.nfs.yaml` (same as Jellyfin).

### 3. Collabora on periphery, WOPI via public Caddy names

Collabora CODE publishes `9980`. `ssl.enable=false`, `ssl.termination=true`, `aliasgroup1` = `https://cloud.{$DOMAIN}:443`. OpenCloud runs `OC_ADD_RUN_SERVICES=collaboration` with `COLLABORATION_APP_ADDR=https://office.{$DOMAIN}` and `COLLABORATION_WOPI_SRC=https://cloud.{$DOMAIN}`. Both containers get `extra_hosts` so `cloud.` / `office.` resolve to `NAS_LAN_IP` (Caddy), because Docker DNS is not Pi-hole.

No Caddy `authelia_gate` on Collabora (WOPI is machine traffic).

**Alternative considered:** Collabora on Core. Rejected: office CPU belongs on the HTPC; Core is 4GB.

### 4. Hostnames and Caddy

| Host | Upstream |
|---|---|
| `cloud.` `oc.` `opencloud.` | `opencloud:9200` on edge |
| `photos.` `immich.` | `{$HTPC_UPSTREAM}:2283` |
| `office.` `collabora.` | `{$HTPC_UPSTREAM}:9980` |
| `nextcloud.` `nc.` | 301 to `cloud.` |

Long read/write timeouts on `cloud.` and `office.` for uploads and WOPI.

### 5. Secrets

Replace bootstrap/Komodo `NEXTCLOUD_*` with `OPENCLOUD_ADMIN_PASSWORD` (`IDM_ADMIN_PASSWORD`) and `IMMICH_DB_PASSWORD`. Existing Core installs add those keys in the Komodo UI (same pattern as `NEXTCLOUD_DB_PASSWORD`).

## Risks / Trade-offs

- **[PosixFS xattrs missing on the OMV disk]** → First-run doc: confirm `user_xattr` on the data filesystem; fail closed rather than switching to DecomposedFS.
- **[OpenCloud UID cannot write `users/<user>` mode 700]** → `data-root-perms.sh` grants `u:${PUID}:rwx` on homes; OpenCloud runs as PUID:PGID.
- **[Collabora cannot reach WOPI / OpenCloud cannot reach Collabora]** → `extra_hosts` to `NAS_LAN_IP`; `OC_INSECURE` / Collabora `ssl.ssl_verification=false`.
- **[Immich NFS inotify]** → Periodic External Library scan, not live watch.
- **[Android generic folder auto-upload missing]** → Camera photos/videos only; share-sheet for other files.
- **[Stale Nextcloud volumes on HTPC]** → Document stop/remove; do not delete NFS photo/file data.

## Migration Plan

1. Add Komodo secrets `OPENCLOUD_ADMIN_PASSWORD`, `IMMICH_DB_PASSWORD`.
2. Sync catalog; deploy `opencloud` (Core), then `immich` and `collabora` (periphery).
3. First-run: OpenCloud admin, household users matching `users/<name>`, Spaces `files`/`photos` if wanted, phone auto-upload destination `photos`.
4. Immich: create admin, External Libraries, disable mobile backup.
5. Remove Nextcloud stack in Komodo; `docker rm` leftover containers/volumes (`nextcloud-config`, `nextcloud-postgres` only).
6. Rollback: restore previous catalog commit and Nextcloud stack; trees on disk are unchanged.

## Open Questions

- None. Authelia OIDC is a later change.
