# OpenCloud first-run (greenfield)

OpenCloud on **Core** (edge): PosixFS **documents** and **camera rolls** only.

| OpenCloud space | On disk | Who uses it |
|---|---|---|
| Personal | `users/<user>/files` | People + SMB |
| `photos-<user>` | `users/<user>/photos` | Phone ingest → Immich |
| `shared` | `shared/files` | Household docs + SMB |

`shared/{media,games,photos,downloads,cameras}` stay on SMB/NFS for Jellyfin/Arr/qBit/Kodi/Immich/Frigate. They are **not** OpenCloud spaces.

**Default path:** empty disk → OpenCloud creates space roots → publish binds → layout.  
**Park/restore** utilities: `opencloud-adopt-homes.sh`, `opencloud-adopt-shared.sh`, `opencloud-adopt-photos.sh`.

## Greenfield checklist

### 0. Topology and host prep

1. Edit `stacks/komodo/topology.inc`. Regenerate: `python3 stacks/komodo/generate-stacks.py`.
2. Bootstrap Core (`core.sh`): Docker, OMV, Komodo, Authelia `users.yml`, **`data-root-prep.sh`**.
3. Komodo secrets include **`OPENCLOUD_ADMIN_PASSWORD`**.

### 1. Phase A ResourceSync

Apply **`stacks/komodo/stacks-bootstrap.toml`**. Redeploy **caddy** if the Caddyfile just gained `cloud.` / `office.`.

```text
docker ps --filter name='opencloud|radicale|collabora|caddy|authelia' --format 'table {{.Names}}\t{{.Status}}'
```

### 2. Login (Personal = files/)

Open `https://cloud.<DOMAIN>` → Authelia as an **admins** user (creates `users/<user>/files`). Then each household user.

`users/admin` is break-glass OpenCloud admin — leave it. Create an **App Token** for CalDAV/clients.

### 3. Space `shared` + publish onto `shared/files`

As an OpenCloud admin: Spaces → New Space → name exactly **`shared`** → add household members.

```text
DATA=/srv/dev-disk-by-uuid-…
sudo getfattr -d $DATA/system/opencloud/projects/shared | grep space.id
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh publish
sudo stat -c '%d:%i' $DATA/shared/files $DATA/system/opencloud/projects/shared
```

### 4. Photos spaces + layout + shares

For each household user: Spaces → New Space → name exactly **`photos-<user>`** (example `photos-faiz`) → add that user.

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-photos.sh publish
sudo DATA_ROOT=$DATA bash bootstrap/data-root-layout.sh
```

Layout creates `shared/media`, household `shared/photos`, `users/<name>/photos` ACLs/sticky. Then OMV SMB/NFS (`bootstrap/omv-nfs.md`) for `shared` and `users`.

Host timer assimilates SMB writes OpenCloud’s inotify miss (`opencloud-posix-scan.timer`). It scans **`/posix/users` and `/posix/projects` only** (not `/posix`, which walks `uploads/` and used to walk media).

```text
sudo bash bootstrap/opencloud-posix-scan.sh
sudo bash bootstrap/core-net.sh
sudo systemctl start opencloud-posix-scan.service
```

### 5. Phase B stacks

Apply **`stacks-core.toml`** and **`stacks-periphery.toml`**. Deploy Immich, Jellyfin, etc.

### 6. Verify

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-check.sh
```

### Collabora / Radicale / phone

- Collabora: catalog `COLLABORATION_APP_PROOF_DISABLE` + `collabora-ca`; open a document once.
- CalDAV: `https://cloud.<DOMAIN>`, username = OpenCloud user, password = App Token.
- Phone auto-upload → space **`photos-<user>`** (the space root, not Personal and not a `CameraUpload` folder). Immich mobile backup off.

---

## Existing site (whole `shared/` was the space)

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh narrow
```

That umounts the old bind, leaves media/games on `shared/`, and rebinds the space onto `shared/files`. Then Redeploy **opencloud** (new Personal template), then:

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh park
# log in as each user
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-photos.sh park
# create Spaces photos-faiz, photos-diana; add that user
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-photos.sh publish
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-photos.sh restore
sudo DATA_ROOT=$DATA bash bootstrap/data-root-layout.sh
sudo bash /tmp/opencloud-posix-scan.sh   # after scp of the new scan script
sudo systemctl start opencloud-posix-scan.service
```

---

## If content already exists (park utilities)

```text
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-homes.sh park
# login each user → restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-shared.sh park
# create Space shared → publish → restore
sudo DATA_ROOT=$DATA bash bootstrap/opencloud-adopt-photos.sh park
# create photos-<user> → publish → restore
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
| `shared/files` empty in UI but SMB has docs | Bind missing — `adopt-shared.sh publish` (inode check), not findmnt alone |
| Whole `shared/` still in OpenCloud | `adopt-shared.sh narrow` |
| OC→SMB works, SMB→OC does not | Install/reinstall `opencloud-posix-scan.sh` (scan users+projects only), `core-net.sh`, start the oneshot |
| `posixfs scan /posix` failed | Expected on the old script (`uploads/` + media). Use the new scanner |
| Collabora white iframe / ProofKeys | Redeploy collabora + opencloud; proof disable + CA |
| `radicale` permission denied | prep should have PUID-owned radicale data |
| Layout sticky missing | Re-run **data-root-layout.sh** after publish |
