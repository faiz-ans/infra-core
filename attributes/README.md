# Attributes (sops/age)

Site values are **not** committed in plaintext. Materia reads encrypted vaults from this directory.

| File | Scope |
|---|---|
| `vault.age` | Shared globals (every host) |
| `core.age` | NAS (`core`) only |
| `mantle.age` | WSL (`mantle`) only |

Age private key is created **on the box** (see bootstrap) and never committed. Example unencrypted schemas live next to this file as `*.example.toml`. Copy, fill, encrypt:

```bash
age -r "$(cat /etc/materia/age.pubkey)" -o attributes/vault.age attributes/vault.example.toml
```

Or use sops (YAML) instead; set `MATERIA_ATTRIBUTES=sops` / a blank `[sops]` in Materia config. Age vaults are TOML; sops vaults are YAML.

## Catalog variables

Do not put live IPs, domains, or secrets in git. Keys:

**Globals (vault):** `DOMAIN`, `TZ`, `NAS_LAN_IP`, `SURFACE_UPSTREAM`, `DATA_ROOT`, `PUID`, `PGID`, `NFS_SHARED` (WSL host path to OMV `shared/`, e.g. `/mnt/nas/shared`), `NFS_USERS`, `BACKUP_DRIVE` (WSL path, e.g. `/mnt/d`), `WG_HOST`, `CORE_SERVER` (always `core`).

**Secrets:** Authelia session/storage/OIDC, `OIDC_CLIENT_SECRET`, Pi-hole passwords (`PIHOLE_WEBPASSWORD`, `PIHOLE_MANTLE_WEBPASSWORD`), Vaultwarden, Restic, Immich DB, Adventure Log, Grafana, NUT, Homepage widget keys (`HOMEPAGE_VAR_*` except those mapped from `DOMAIN` / `SURFACE_UPSTREAM` / `NAS_LAN_IP` / `TZ`).

`HOMEPAGE_VAR_SURFACE_UPSTREAM` is mapped from `SURFACE_UPSTREAM` in the Homepage Quadlet. `HOMEPAGE_VAR_PIHOLE_MANTLE_TOKEN` maps from `PIHOLE_MANTLE_WEBPASSWORD`. There is no `HOMEPAGE_VAR_KOMODO_*`.

## Materia

Pin **Materia v0.7.2**. Timer only (`materia update`); do not run `materia server` on this site. Core runs a **system** timer (nft, `wg-quick`, Scrutiny) and a **user** timer as `pilot` (rootless Quadlets). Mantle runs a **user** timer as Linux `pilot`. Point Materia at the catalog git remote you use (this site: GitHub). No GitHub webhooks.
