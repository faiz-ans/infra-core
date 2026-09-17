# infra-core

Public catalog, environment-agnostic. Site values live in `/etc/infra-core/site.env` on the box (never git). Host assignment is [`MANIFEST.toml`](MANIFEST.toml). Apply with [`bootstrap/apply.sh`](bootstrap/apply.sh). Materia is an optional poller, not Layer 0.

## Names

| Hostname | What |
|---|---|
| `core` | NAS. Admin `pilot`. |
| `surface` | Windows 11 TV PC. Admin `pilot`. Ethernet `SURFACE_UPSTREAM`. |
| `mantle` | Ubuntu WSL2 on `surface`. Linux `pilot`. Windows owner: `HTPC`. |

## Layers

```
Layer 0  bootstrap/core.sh   OMV (optional), Podman, Cockpit, site.env
Layer 1  bootstrap/apply.sh  Quadlets from MANIFEST.toml roles
Layer 2  this repo           components/ + windows/
```

Optional: [`bootstrap/core/materia-enable.sh`](bootstrap/core/materia-enable.sh) (`git pull && apply.sh`). Kubernetes is a future consumer of the same kube-play YAML (`overlays/k8s/` stub). This site never runs Kubernetes.

## Target state

```
${DATA_ROOT}/
  system/<app>
  shared/{media,downloads,files,photos,cameras}
  users/<user>/{files,photos}
```

## Bootstrap order

Follow **[`bootstrap/SITE-DEPLOY.md`](bootstrap/SITE-DEPLOY.md)** (flash OS only, remount data disk, phase A, lan-bind, OpenCloud/layout/NFS, phase B). Do not export Docker volumes or purge Komodo.

Winget: [`windows/packages.json`](windows/packages.json).

## Variable keys

See [`attributes/README.md`](attributes/README.md) for optional age vaults (Materia only). Default apply uses `/etc/infra-core/site.env`.
