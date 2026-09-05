# OpenCloud first-run

OpenCloud on **Core** (edge): PosixFS personal homes under `users/<username>/`, household Project Space **`shared`** (name exact) under `system/opencloud/projects/shared`, bind-mounted onto `${DATA_ROOT}/shared` for SMB/NFS. Collabora on periphery (`office.<DOMAIN>`). Radicale in the same stack for CalDAV/CardDAV. Immich still indexes `shared/photos` over NFS.

Follow this checklist **in order**. Do not bind `shared/` as the space root, and do not nest `shared/files` or `shared/photos` mounts. Failure recovery is in the appendix at the bottom.

## 0. Prerequisites

- Authelia users **faiz** / **diana** exist (`bootstrap/authelia.md`).
- Komodo secret **`OPENCLOUD_ADMIN_PASSWORD`** set (new sites: `core.sh` writes it).
- Catalog synced; **caddy** Redeployed if the Caddyfile just gained `cloud.` / `office.`.

```text
sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root-perms.sh
```

That creates layout dirs, ACLs, and PUID-owned `system/opencloud/{posix,projects,radicale}`.

## 1. Deploy

Komodo → **opencloud** → **Deploy**. Periphery → **collabora** → **Deploy**.

```text
docker ps --filter name='opencloud|radicale|collabora' --format 'table {{.Names}}\t{{.Status}}'
```

Want: `opencloud` Up, `radicale` Up, `collabora` Up, `collabora-ca` Up (healthy). OpenCloud must **not** publish 9200 on the LAN.

## 2. Login and roles

Open `https://cloud.<DOMAIN>` → Authelia as **faiz**. Roles come from Authelia groups (`admins` → OpenCloud admin, `users` → user). Sign out/in once after first Deploy if Spaces UI is empty.

Built-in **`admin`** / `OPENCLOUD_ADMIN_PASSWORD` is break-glass (DAV / App Tokens via basic auth), not the browser login while OIDC is on. `users/admin` on disk is that Personal space — leave it; household homes are only **faiz** and **diana**.

Create an **App Token** for CalDAV/CardDAV and most mobile clients.

## 3. Personal homes (adopt)

Pre-created `users/<name>` blocks CreateStorageSpace (path exists, no xattrs). Always park → login → restore on a site that already ran `data-root-perms`:

```text
DATA=/srv/dev-disk-by-uuid-…
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh park
# Browser: sign in as faiz, then diana (each creates users/<name> + space xattrs)
sudo getfattr -d $DATA/users/faiz | grep space.id
sudo getfattr -d $DATA/users/diana | grep space.id
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh restore
```

If a home is “missing” but perms said **parked**, content is under `system/opencloud/incoming/<user>` — finish login + restore; do not mkdir a stub.

## 4. Household Space `shared` (adopt)

Same rule: do **not** bind `${DATA_ROOT}/shared` as `/posix/projects/shared`. Catalog uses parent bind `system/opencloud/projects` → `/posix/projects`.

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh park
# Komodo → opencloud → Redeploy if the stack was never on the projects parent bind
# Browser (faiz): Spaces → New Space → name exactly shared → add diana
sudo getfattr -d $DATA/system/opencloud/projects/shared | grep space.id
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh publish
# publish MUST report same inode (not “already mounted” via findmnt alone)
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh restore
```

`publish` bind-mounts `projects/shared` → `shared/` and adds an `/etc/fstab` line (`# opencloud-shared-bind`). `restore` merges parked content and runs `posixfs scan` (large media/games trees take time).

## 5. ACLs and protected layout dirs

After every home/shared restore:

```text
sudo DATA_ROOT=$DATA bash bootstrap/data-root-perms.sh
```

This restores household ACLs and root-owns service layout dirs (media, cameras, `files`/`photos`, games layout, …) with sticky parents so SMB/OpenCloud can write **inside** them but cannot rename/delete those nodes. Reconnect SMB sessions afterward. Do **not** put Samba `force user` on the household `shared` share.

## 6. Collabora (office)

Catalog already sets `COLLABORATION_APP_PROOF_DISABLE=true` and Collabora mounts a generated `proof_key` plus Caddy CA bundle (`collabora-ca`). After **collabora** is healthy, open a document from OpenCloud once.

## 7. Calendar / contacts (Radicale)

URL: `https://cloud.<DOMAIN>` (well-known). Username = OpenCloud username (`faiz`, not an email). Password = **App Token**. No calendar UI in OpenCloud.

## 8. Phone auto-upload

App server: `https://cloud.<DOMAIN>`. Upload target: Personal → **`photos`**. Leave Immich mobile backup off.

## 9. Verify

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-check.sh
```

Exit 0 means containers, space xattrs, shared bind, sticky sample, Radicale ownership, and proof-disable look ready. Fix anything it prints, then re-run.

Optional: `sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh status` and `…/opencloud-adopt-shared.sh status`.

---

## Appendix: if it fails

| Symptom | What to do |
|---|---|
| `cloud.<DOMAIN>` dead while `opencloud` Up | Redeploy **caddy**. `docker exec caddy wget -S -O- --timeout=10 http://opencloud:9200/ \| head` |
| `posixfs-xattr-check` / `storage/metadata: permission denied` | Stop opencloud; `chown -R ${PUID}:${PGID}` `system/opencloud`; ensure `posix/` exists; Redeploy |
| `error parsing mapping JSON` / search | Stop; `rm -rf system/opencloud/data/search`; start |
| Login HTTP 500 | Wipe **both** `system/opencloud/config` and `…/data` (not `posix`, `users`, `shared`, `radicale`); start so `init` reseeds. Use `find … -mindepth 1 -delete`, not a glob |
| `extended attributes not supported` | Data disk needs `user_xattr`; keep OpenCloud on Core local disk |
| Permission denied on homes / SMB lost on `shared` | `data-root-perms.sh`; check sticky (`t`/`T`) and root-owned layout nodes |
| No Personal / Spaces empty for faiz | `adopt-homes.sh park` → login each user → `restore`; confirm `user.oc.space.id` |
| Space create / `node.Xattrs …/photos` | No nested `files`/`photos` mounts; one Space named **`shared`** |
| `shared` empty in UI but SMB has files | Bind never took: content in real `shared/`, space is empty `projects/shared`. Move content into `projects/shared`, empty `shared/`, `mount --bind`, confirm same inode, scan |
| `publish` said already mounted but inodes differ | Old script used `findmnt`; use current adopt-shared (inode check) |
| Collabora white iframe / local issuer | Redeploy **collabora**; `collabora-ca` must write `ca-bundle.crt` |
| Collabora Unauthorized WOPI / ProofKeys failed | Need `COLLABORATION_APP_PROOF_DISABLE` + `proof_key` volume; Redeploy opencloud then collabora |
| Collabora Unhealthy | CODE probe expects HTTPS; catalog disables healthcheck. `collabora-ca` must stay Up |
| CalDAV discovery fails | App Token; `wget` `.well-known/caldav` via caddy→opencloud |
| `radicale` permission denied on collections | `chown -R ${PUID}:${PGID}` the radicale data bind (see `docker inspect`); `data-root-perms` should have done this |
| Radicale `IsADirectoryError` on config | Official bind must be a **file** `config/radicale/config`; remove leftover dirs in the stack clone; Redeploy |
| Secret mismatch after change | `IDM_ADMIN_PASSWORD` only applies on init; `opencloud idm resetpassword` or wipe config+data |

### Manual config/data wipe (last resort)

```text
sudo docker stop opencloud
sudo find $DATA/system/opencloud/config -mindepth 1 -delete
sudo find $DATA/system/opencloud/data -mindepth 1 -delete
sudo chown -R 1000:1000 $DATA/system/opencloud
sudo docker start opencloud
sudo docker logs -f opencloud   # must show init, not “config already exists”
```

### Remove leftover Nextcloud

After ResourceSync drops `nextcloud`, delete that stack. On HTPC stop/rm containers and config volumes only — **not** NFS `shared/` / `users/` data.
