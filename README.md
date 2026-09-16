# infra-core

Public catalog, environment-agnostic. Site values live in sops/age attributes on-box (`attributes/`). Host assignment is [`MANIFEST.toml`](MANIFEST.toml). Materia clones whatever git remote you configure on the box (this site uses GitHub). No GitHub webhooks.

## Names

| Hostname | What |
|---|---|
| `core` | NAS. Admin `pilot`. Materia host. |
| `surface` | Windows 11 TV PC. Admin `pilot`. Ethernet `SURFACE_UPSTREAM`. |
| `mantle` | Ubuntu WSL2 on `surface`. Linux `pilot`. Materia + Podman. Windows owner: `HTPC`. |

## Layers

```
Layer 0  bootstrap/     OMV (optional), purge Docker/Komodo, Podman, Cockpit, Materia timers
Layer 1  Materia        attributes + MANIFEST.toml; systemd Quadlets; no GitHub webhooks
Layer 2  this repo      components/ + windows/
```

Kubernetes is a future consumer of the same kube-play YAML (`overlays/k8s/` stub). This site never runs Kubernetes.

## Target state

```
${DATA_ROOT}/
  system/<app>                         # Core bind-mounts only (not system/core)
  shared/{media,downloads,files,photos,cameras}
  users/<user>/{files,photos}
```

- Restic: [`bootstrap/first-run/restic.md`](bootstrap/first-run/restic.md) (`BACKUP_DRIVE` is the surface USB).
- mantle `/config` is a local Podman volume. Libraries use WSL NFS of `shared/` and `users/`.
- Pi-hole: `pihole` on core, `pihole-mantle` on mantle.
- Core IPv4 is static (`NAS_LAN_IP`). surface Ethernet is static (`SURFACE_UPSTREAM`).
- Router DHCP DNS: Core first, surface second. No public resolver as a third.
- WireGuard data plane is host `wg-quick` on Core. wg-easy UI is rootless on `:51821`. Client MTU 1280. Do not forward RustDesk 21115–21119.

## Bootstrap order

1. **surface** wipe / restore Kodi+Firefox / idle `mantle` while Core still has DNS/Caddy — [`windows/kodi-firefox-cutover.md`](windows/kodi-firefox-cutover.md).
2. Clone this catalog onto Core from your git remote.
3. Core: export leftover Docker volumes (Caddy `/data`) → `sudo bash bootstrap/core.sh` (purge + Podman + Materia). First apply is `core-bootstrap` (edge + OpenCloud).
4. OpenCloud publish → `data-root/data-root-layout.sh` → OMV NFS/SMB.
5. mantle: [`bootstrap/mantle/README.md`](bootstrap/mantle/README.md) then Materia `[Hosts.mantle]`.
6. Cockpit on Core (`https://box.<DOMAIN>` or `:9090`). No required mantle Cockpit. No `ops.` Komodo vhost.

Winget: [`windows/packages.json`](windows/packages.json).

## Variable keys

See [`attributes/README.md`](attributes/README.md). Do not put values in this repository.
