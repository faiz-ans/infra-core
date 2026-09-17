# Site deploy

From-scratch Core: new OS disk, remount or format-empty `DATA_ROOT`, `core.sh`, then `apply.sh`. This is **not** a Docker/Komodo move. Site values live in `/etc/infra-core/site.env` (never git). Live IPs, domains, and disk UUIDs stay out of this repository.

Materia is **optional** (`bootstrap/core/materia-enable.sh`) and is not Layer 0.

## This site’s exceptions

- Do **not** wipe the NAS data disk. Remount it. Prove `users/`, `shared/`, and `system/vaultwarden` exist before `core.sh`.
- Re-insert saved Caddy PKI, Authelia `users.yml` (not sqlite), Homepage YAML if it differs from git, Vaultwarden live dir or JSON import if empty.

## 0. Copy configs off-box

Copy tarballs of `system/caddy`, Authelia file-backend files, Vaultwarden (dir + JSON export), WireGuard, and `/etc/infra-core` (or the previous `/etc/materia` age key if you will enable Materia later) onto a laptop or USB that is **not** the data disk and **not** the Restic backup disk.

## 1. Catalog

Apply this catalog on git (`podman-rewrite-2` or later). Do not flash onto an unpatched HEAD.

## 2. Flash the OS disk only

Image Raspberry Pi OS Lite 64-bit onto the **OS** media. hostname `core`, user `pilot`, SSH on. Unplug the Restic USB. Do not format the data disk.

## 3. Remount and prove data

```text
lsblk -o NAME,SIZE,MODEL,TRAN,FSTYPE,UUID,MOUNTPOINT
sudo mkdir -p /srv/dev-disk-by-uuid-<UUID>
sudo mount UUID=<UUID> /srv/dev-disk-by-uuid-<UUID>
sudo ls $DATA/users $DATA/shared $DATA/system/vaultwarden $DATA/system/caddy $DATA/system/authelia/users.yml
```

If those paths are missing, you mounted the wrong disk. Stop. `core.sh` will format **only** a disk with no ext4, and only if you type `YES`.

## 4. Layer 0

```text
git clone <catalog-remote>
sudo mkdir -p /etc/infra-core
# optional: restore bootstrap-answers.env so DOMAIN/NAS_LAN_IP are not re-typed
sudo bash bootstrap/core.sh
```

Confirm `/etc/infra-core/site.env` (`DOMAIN`, `NAS_LAN_IP`, `SURFACE_UPSTREAM`, `WG_HOST`, `DATA_ROOT`). Materia is not installed. Layer 0 chowns `system/authelia` to `PUID` so rootless Authelia can read `oidc.pem`.

## 5. Phase A

```text
sudo bash bootstrap/apply.sh --role core-bootstrap
ss -lntup | grep -E ':15353|:8080|:8443|:9091'
```

`core-bootstrap` is site-network, Caddy, Authelia, Pi-hole, Glances, PeaNUT, Homepage, OpenCloud.

PeaNUT must come up host-net on `:8092` (NUT `127.0.0.1:3493`). Browser `https://ups.<DOMAIN>`. Homepage tile scrapes `http://169.254.1.2:8092`. Do not put PeaNUT on `site` or on host `:8080`. Details: `bootstrap/first-run/peanut.md`.

Restore Caddy PKI / Authelia users from the off-box copy only if the remounted tree is missing them.

## 6. Lan-bind

```text
sudo bash bootstrap/core/core-lan-bind.sh --enable
getent hosts github.com
```

Router DHCP DNS: Core first, surface second. No public third.

## 7. OpenCloud, layout, NFS

Layer 0 already installed `attr` (`getfattr`) and enabled `opencloud-posix-scan.timer` (SMB/NFS writes into OpenCloud). Layout starts a catch-up scan. Do not install packages or the scan script by hand.

Scripts below read `DATA_ROOT` and `SURFACE_UPSTREAM` from `/etc/infra-core/site.env`.

**Existing data disk (this site):** do **not** create spaces if xattrs are present.

```text
sudo bash -c 'set -a; source /etc/infra-core/site.env; set +a
getfattr -n user.oc.space.id --only-values "$DATA_ROOT/users/faiz/files"
getfattr -n user.oc.space.id --only-values "$DATA_ROOT/users/diana/files"
getfattr -n user.oc.space.id --only-values "$DATA_ROOT/system/opencloud/projects/shared"'
sudo bash bootstrap/data-root/data-root-layout.sh
sudo bash bootstrap/omv/omv-nfs.sh
sudo bash bootstrap/opencloud/opencloud-check.sh
```

UUIDs from `getfattr` mean the remounted spaces are intact. Park/adopt only if `system/opencloud/{config,data}` is corrupt (`bootstrap/first-run/opencloud.md`).

**Empty disk:** Authelia login at `https://cloud.<DOMAIN>` → create Space `shared` → `sudo bash bootstrap/opencloud/opencloud-adopt-shared.sh publish` → photos spaces `photos-faiz` / `photos-diana` (only that user Can manage) → layout → NFS → check (same three scripts as above). Details: `bootstrap/first-run/opencloud.md`.

`ls /export/shared/media` on Core must list content. Mantle NFS smoke: `bootstrap/omv/README.md` §4.

## 8. Phase B

Edit `MANIFEST.toml`: `[Hosts.core] Roles = ["core-bootstrap", "core-full"]`. Then:

```text
sudo bash bootstrap/apply.sh --role core-full
```

Vaultwarden: use the live dir if present; import JSON only if empty. Then `SIGNUPS_ALLOWED=false` and re-apply vaultwarden.

## 9. Optional Materia

Only if this lab still wants git-poll:

```text
sudo bash bootstrap/core/materia-enable.sh
```

That timer runs `git pull && apply.sh`. It must not render `.gotmpl`. Skip on a static future site.

## 10. Mantle later

Idle mantle until Core DNS/Caddy/OpenCloud/NFS are boring. Then `bootstrap/mantle/README.md`, `apply.sh --role mantle-bootstrap` (Collabora), then `mantle-full`. Do not re-wipe Windows for this rewrite.
