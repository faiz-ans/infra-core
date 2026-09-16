# Layer 0

Copy this directory onto Core and run `core.sh` as root.

Cutover order: **surface wipe / idle mantle while Core still serves DNS/Caddy** → land this catalog on git → **Core purge + Podman/Materia** → **mantle Materia apply**.

| Path | What |
|---|---|
| `core.sh` | NAS bootstrap (OMV, purge Docker/Komodo, Podman, Cockpit, Materia) |
| `core/` | static LAN, :53/:80/:443 bind, cage fan, Materia install/purge |
| `data-root/` | `DATA_ROOT` tree (prep before OpenCloud, layout after publish) |
| `omv/` | OMV NFS/SMB exports, IronWolf disk migrate, USB UPS (NUT) |
| `opencloud/` | Space adopt, PosixFS assimilate timer, readiness check (`podman exec`) |
| `surface/` | Windows Ethernet pin, USB backup disk |
| `mantle/` | WSL2 Podman, host NFS, CDI GPU, user Materia as `pilot` |
| `first-run/` | Per-app first-run notes (systemd / `podman`, not Komodo Deploy) |

Materia pin: **v0.7.2**. Age key: `/etc/materia/age.key`. Host names: `core` / `mantle` (`surface` is Windows only).
