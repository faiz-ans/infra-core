# infra-core

Public catalog, environment-agnostic. Site values (domain, IPs, disk paths, secrets, server names) live only in Komodo on-site. Stack-to-server placement is declared in [`stacks/komodo/topology.inc`](stacks/komodo/topology.inc) and generated into ResourceSync TOML. **Gitea on Core is origin**; GitHub is a push mirror (see [`bootstrap/gitea.md`](bootstrap/gitea.md)).

## Layers

```
Layer 0  bootstrap/     OMV (optional), Docker, Komodo Core + local Periphery;
                        remote Docker engine + outbound Periphery
Layer 1  Komodo         Variables and secrets; polls git; no GitHub webhooks
Layer 2  this repo      stacks/ + windows/
```

Komodo server names in generated ResourceSync TOML are literals from topology (this reference site: **`core`** and **`periphery`**). Komodo does not interpolate `[[VAR]]` on `server`/`repo`. Bootstrap `CORE_SERVER` / `PERIPHERY_SERVER` must match. Edit topology and run `python3 stacks/komodo/generate-stacks.py` (see [`stacks/komodo/README.md`](stacks/komodo/README.md)). Stacks clone GitHub themselves. ResourceSync Selects the Komodo Repo named **`infra-core`**. Komodo Core is on `edge` and the compose default network; default is the internet gateway so GitHub and `gitea:3000` both work (see `bootstrap/komodo/compose.yaml`).

## Target state (after bootstrap + ResourceSync)

A finished site matches this layout. Do not reintroduce `system/core` or `system/periphery`, or an NFS export of the disk root.

```
${DATA_ROOT}/
  system/{authelia,vaultwarden,gitea,pihole,wireguard,restic,opencloud,jotty,linkding,rustdesk,bytestash}   # Core bind-mounts only
  shared/{media,downloads,files,photos,cameras}           # NFS /shared (files/ is OpenCloud; rest is HTPC/SMB)
  users/<user>/{files,photos}                             # NFS /users (OpenCloud Personal + photos-<user>)
```

- Komodo: `NFS_EXPORT=/shared`, `NFS_USERS=/users`. `restic` and `restic-rest` stay `deploy = false` until `BACKUP_DRIVE` is ready.
- HTPC `/config` is a local Docker volume. Media stacks use NFS. OpenCloud on Core bind-mounts `users/` and `system/opencloud/projects/`; host binds those space leaves onto `shared/files` and `users/<user>/photos`.
- ResourceSync names are global: Core Pi-hole is `pihole`, HTPC is `pihole-periphery`.
- Core host IPv4 is static (`NAS_LAN_IP` on the LAN NIC via NetworkManager). A router DHCP reservation is not required and is not sufficient after a cold plug of a USB NIC.
- Router DHCP DNS: Core LAN IP first, HTPC second. No public resolver as a third server. Each Pi-hole fetches its own Gravity.
- WireGuard is host-network on Core. Caddy (`edge`) proxies the VPN UI to the host. Router: UDP 51820 to Core only. Do not forward RustDesk 21115–21119; off-LAN desktop is WireGuard. `WG_HOST` is a public DNS name (not `DOMAIN` if that would make Pi-hole steal the endpoint). Client MTU 1280 (catalog rewrites wg-easy’s factory 1420).

## Bootstrap order (greenfield)

1. **Topology:** edit `stacks/komodo/topology.inc`, regenerate TOML (`stacks/komodo/README.md`).
2. Copy `bootstrap/` to Core; run `core.sh` as root. It runs **`data-root-prep.sh`** (system/ + empty users/ + OpenCloud dirs), not full household layout.
3. Komodo: confirm `core`. ResourceSync path **`stacks/komodo/stacks-bootstrap.toml`** first (phase A: Caddy, Authelia, Pi-hole, Homepage, OpenCloud, Collabora, …). Homepage for a new site: copy `stacks/platform/homepage/config.seed/` → `config/` once (never overwrite a customized `config/`).
4. OpenCloud greenfield: login (Personal = `users/<user>/files`) → Spaces **`shared`** and **`photos-<user>`** → publish binds → **`data-root-layout.sh`** → OMV SMB/NFS (`bootstrap/omv-nfs.md`). Details: [`bootstrap/opencloud.md`](bootstrap/opencloud.md). Check: `bootstrap/opencloud-check.sh`.
5. Periphery host: [`bootstrap/periphery.md`](bootstrap/periphery.md). Then ResourceSync **`stacks-core.toml`** + **`stacks-periphery.toml`** (phase B). First HTPC bring-up: Deploy one stack at a time (`deploy = false` in periphery fragments). Authelia SSO: [`bootstrap/authelia.md`](bootstrap/authelia.md). Other apps: matching files under `bootstrap/`.

Existing site: add the bootstrap TOML path without reshuffling stack names ([`stacks/komodo/README.md`](stacks/komodo/README.md) migration). Park scripts remain for non-empty disks.

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
