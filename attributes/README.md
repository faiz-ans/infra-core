# Site values

Default apply reads **`/etc/infra-core/site.env`** on the box (`bootstrap/apply.sh`). That file is never committed.

Encrypted vaults in this directory are **optional** and only used if you later enable Materia (`bootstrap/core/materia-enable.sh`). Layer 0 does not create `/etc/materia` or an age key.

| File | Scope |
|---|---|
| `vault.example.toml` | Shared globals schema (copy; do not commit filled values) |
| `core.example.toml` | NAS (`core`) extras |
| `mantle.example.toml` | WSL (`mantle`) extras |
| `vault.age` / `core.age` / `mantle.age` | Optional encrypted vaults (Materia only) |

If you enable Materia, generate the age key **on the box** and never commit it:

```bash
age -r "$(cat /etc/materia/age.pubkey)" -o attributes/vault.age attributes/vault.example.toml
```

## Catalog variables

Do not put live IPs, domains, or secrets in git. Keys (written by `core.sh` or by hand into `site.env`):

**Globals:** `DOMAIN`, `TZ`, `NAS_LAN_IP`, `SURFACE_UPSTREAM`, `DATA_ROOT`, `PUID`, `PGID`, `NFS_SHARED` (WSL host path to OMV `shared/`, e.g. `/mnt/nas/shared`), `NFS_USERS`, `BACKUP_DRIVE` (WSL path, e.g. `/mnt/d`), `WG_HOST`, `CORE_SERVER` (always `core`), `HOMEPAGE_ALLOWED_HOSTS`.

**Secrets:** Authelia session/storage/OIDC, `OIDC_CLIENT_SECRET`, Pi-hole passwords (`PIHOLE_WEBPASSWORD`, `PIHOLE_MANTLE_WEBPASSWORD`), Vaultwarden, Restic, Immich DB, Adventure Log, Grafana, NUT, Homepage widget keys (`HOMEPAGE_VAR_*` except those mapped from `DOMAIN` / `SURFACE_UPSTREAM` / `NAS_LAN_IP` / `TZ`).

`HOMEPAGE_VAR_SURFACE_UPSTREAM` is mapped from `SURFACE_UPSTREAM` in the Homepage Quadlet. `HOMEPAGE_VAR_PIHOLE_MANTLE_TOKEN` maps from `PIHOLE_MANTLE_WEBPASSWORD`. There is no `HOMEPAGE_VAR_KOMODO_*`.

## Optional Materia

Skip this on a static future site. If this lab still wants git-poll, `materia-enable.sh` installs a timer that runs `git pull && apply.sh` (not a second Quadlet renderer). Age vaults remain optional even then.
