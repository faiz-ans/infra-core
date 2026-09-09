# OpenCloud first-run (greenfield)

OpenCloud on **Core** (edge): PosixFS personal homes under `users/<username>/`, household Project Space **`shared`** under `system/opencloud/projects/shared`, bind-mounted onto `${DATA_ROOT}/shared` for SMB/NFS. Collabora on its topology-assigned server (`office.<DOMAIN>`). Radicale ships in the OpenCloud stack.

**Default path:** empty disk → OpenCloud creates space roots → publish → layout.  
**Park/restore** (`opencloud-adopt-homes.sh`, `opencloud-adopt-shared.sh`) are utilities when homes or `shared/` content already exist. Failure recovery is in the appendix.

## Greenfield checklist

### 0. Topology and host prep

1. Edit `stacks/komodo/topology.inc` (servers + stack phases). Regenerate: `python3 stacks/komodo/generate-stacks.py` (see `stacks/komodo/README.md`).
2. Bootstrap Core (`core.sh`): Docker, OMV, Komodo, Authelia `users.yml`, **`data-root-prep.sh`** (`system/`, empty `users/`, OpenCloud host dirs).
3. Komodo secrets include **`OPENCLOUD_ADMIN_PASSWORD`**.

### 1. Phase A ResourceSync

Apply **`stacks/komodo/stacks-bootstrap.toml`** only (Caddy, Authelia, Pi-hole, Glances, Homepage, OpenCloud, Collabora as assigned). Redeploy **caddy** if the Caddyfile just gained `cloud.` / `office.`.

New Homepage: copy `stacks/platform/homepage/config.seed/*` → `config/` once (do not overwrite a customized site).

```text
docker ps --filter name='opencloud|radicale|collabora|caddy|authelia' --format 'table {{.Names}}\t{{.Status}}'
```

### 2. Login and roles

Open `https://cloud.<DOMAIN>` → Authelia as an **admins** user (creates Personal space + xattrs). Then each household user. Roles: Authelia `admins` → OpenCloud admin, `users` → user.

`users/admin` on disk is break-glass OpenCloud admin — leave it. Create an **App Token** for CalDAV/clients.

### 3. Space `shared` + publish

As an OpenCloud admin: Spaces → New Space → name exactly **`shared`** → add household members.

```text
DATA=/srv/dev-disk-by-uuid-…
sudo getfattr -d $DATA/system/opencloud/projects/shared | grep space.id
# shared/ mountpoint must be empty (no media tree yet)
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh publish
# same inode required
sudo stat -c '%d:%i' $DATA/shared $DATA/system/opencloud/projects/shared
```

### 4. Protected layout + shares

```text
sudo DATA_ROOT=$DATA bash bootstrap/data-root-layout.sh
```

Creates `shared/media`, `photos`, `users/<name>/files|photos`, ACL/sticky. Then OMV SMB/NFS (`bootstrap/omv-nfs.md`) for `shared` and `users`.

Optional scan: `sudo docker exec opencloud opencloud posixfs scan /posix`

### 5. Phase B stacks

Apply **`stacks-core.toml`** and **`stacks-periphery.toml`** (or generated per-server files). Deploy Immich, Jellyfin, etc.

### 6. Verify

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-check.sh
```

### Collabora / Radicale / phone

- Collabora: catalog `COLLABORATION_APP_PROOF_DISABLE` + `collabora-ca`; open a document once.
- CalDAV: `https://cloud.<DOMAIN>`, username = OpenCloud user, password = App Token.
- Phone upload → Personal **`photos`**. Immich mobile backup off.

---

## If content already exists (park utilities)

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh park
# login each user → restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh park
# create Space shared → publish → restore
sudo DATA_ROOT=$DATA bash bootstrap/data-root-layout.sh
```

---

## Appendix: if it fails

| Symptom | What to do |
|---|---|
| `cloud.<DOMAIN>` dead while `opencloud` Up | Redeploy **caddy** |
| Permission / xattr on first start | Re-run **prep**; `chown` OpenCloud dirs to PUID |
| Login HTTP 500 | Wipe **both** `system/opencloud/config` and `…/data` (not posix/users/shared/radicale) |
| No Personal / no space id | Path already existed — use **park** utilities |
| `shared` empty in UI but SMB has files | Bind missing — fix publish (inode check), not findmnt alone |
| Collabora white iframe / ProofKeys | Redeploy collabora + opencloud; proof disable + CA |
| `radicale` permission denied | prep should have PUID-owned radicale data |
| Layout sticky missing | Re-run **data-root-layout.sh** after publish |
