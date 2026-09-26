# Layer 0

Canonical operator path: **[`SITE-DEPLOY.md`](SITE-DEPLOY.md)**.

Copy this directory onto Core and run `core.sh` as root. Then `apply.sh --role core-bootstrap`. Materia is not part of Layer 0.

| Path | What |
|---|---|
| `SITE-DEPLOY.md` | From-scratch (and this site’s remount) runbook |
| `core.sh` | NAS Layer 0 (OMV, Podman, Cockpit, `site.env`) |
| `apply.sh` | Install Quadlets for a role |
| `core/` | static LAN, disabled lan-bind, cage fan, Podman install, optional Materia |
| `data-root/` | prep before OpenCloud, layout after publish |
| `omv/` | NFS/SMB, NUT; `ironwolf-migrate.md` is lab history |
| `opencloud/` | Space adopt, PosixFS assimilate, readiness check |
| `surface/` | Windows Ethernet pin, USB backup disk |
| `mantle/` | WSL2 Podman, host NFS, CDI GPU; optional Materia |
| `first-run/` | Per-app notes (`apply.sh` / systemd) |

Age key (optional Materia only): `/etc/materia/age.key`. Default site env: `/etc/infra-core/site.env`. Host names: `core` / `mantle` (`surface` is Windows only).
