# infra-core

Public catalog, environment-agnostic, for a two-host homelab. Site values (domain, IPs, disk paths, secrets, server names) live only in Komodo on-site. This git repo has compose files, config templates, and ResourceSync TOML. **Gitea on Core is origin**; GitHub is a push mirror (see [`bootstrap/gitea.md`](bootstrap/gitea.md)).

## Layers

```
Layer 0  bootstrap/     OMV (optional), Docker, Komodo Core + local Periphery;
                        remote Docker engine + outbound Periphery
Layer 1  Komodo         Variables and secrets; polls git; no GitHub webhooks
Layer 2  this repo      stacks/ + windows/
```

Komodo server names in ResourceSync TOML are literals **`core`** and **`periphery`** (Komodo does not interpolate `[[VAR]]` on `server` or `repo`). Bootstrap `CORE_SERVER` / `PERIPHERY_SERVER` must match those names. Stack `repo` is the catalog path `faiz-ans/infra-core` (Gitea; GitHub mirror keeps the same name). After Gitea exists, set `git_provider = "gitea:3000"` (see `bootstrap/gitea.md`). Environment values still use `[[VAR]]` at deploy.

## Target state (after bootstrap + ResourceSync)

A finished site matches this layout. Bootstrap creates it; do not reintroduce `system/core` or `system/periphery`, or an NFS export of the disk root.

```
${DATA_ROOT}/
  system/{authelia,vaultwarden,gitea,pihole,wireguard,restic,opencloud,jotty,linkding,rustdesk}   # Core bind-mounts only
  shared/{media,downloads,files,photos,cameras}           # NFS /shared
  users/<user>/{files,photos}                             # NFS /users
```

- Komodo: `NFS_EXPORT=/shared`, `NFS_USERS=/users`. `restic` and `restic-rest` stay `deploy = false` until `BACKUP_DRIVE` is the IronWolf.
- HTPC `/config` is a local Docker volume. Media, downloads, Immich photo originals, and Frigate recordings stay on NFS. OpenCloud on Core bind-mounts `users/` and `shared/` locally.
- ResourceSync names are global: Core Pi-hole is `pihole`, HTPC is `pihole-periphery`.
- Router DHCP DNS: Core LAN IP first, HTPC second. No public resolver as a third server. Each Pi-hole fetches its own Gravity.
- WireGuard is host-network on Core. Caddy (`edge`) proxies the VPN UI to the host. Router: UDP 51820 to Core only. Do not forward RustDesk 21115–21119; off-LAN desktop is WireGuard. `WG_HOST` is a public DNS name (not `DOMAIN` if that would make Pi-hole steal the endpoint). Client MTU 1280 (catalog rewrites wg-easy’s factory 1420).

## Bootstrap order

1. Copy the `bootstrap/` directory (including `core.sh`, `omv-nfs.sh`, `data-root-perms.sh`, and `komodo/`) to the Core host and run `core.sh` as root (or follow the commented commands). Storage is configured first; site prompts come after any OMV reboot. With OMV present, the script exports `shared/` and `users/` to the HTPC IP and applies `data-root-perms.sh`.
2. In Komodo, confirm the `core` server. Secrets from bootstrap live in `/etc/komodo/core.config.toml`. Create a ResourceSync (webhooks off) with resource path `stacks/komodo/stacks-core.toml` first, then apply. After Gitea is up, follow [`bootstrap/gitea.md`](bootstrap/gitea.md) so polls use `gitea:3000` and GitHub is only a mirror.
3. Keep SMB for Explorer/Finder. If you skipped OMV (OS-disk `DATA_ROOT`), export `shared/` and `users/` yourself (`bootstrap/omv-nfs.md`). On the remote host, follow [`bootstrap/periphery.md`](bootstrap/periphery.md) **in order**: Docker Desktop, Engine JSON (`bootstrap/periphery-docker-engine.ps1`), outbound Periphery with `PERIPHERY_CONNECT_AS=periphery`. Leave `restic` / `restic-rest` off until the IronWolf is the backup disk (`BACKUP_DRIVE`).
4. Confirm that server in Komodo, add `stacks/komodo/stacks-periphery.toml` to the same ResourceSync (or a second one), and apply. Home Assistant uses a local volume; `trusted_proxies` is written at start. The other HTPC apps use NFS for household data only. OpenCloud first-run: [`bootstrap/opencloud.md`](bootstrap/opencloud.md). Immich External Libraries: [`bootstrap/immich.md`](bootstrap/immich.md). Jotty / Linkding / RustDesk / Adventure Log / Scriberr / Frigate: matching files under `bootstrap/`.

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
