# Layer 0

Copy this directory onto Core and run `core.sh` as root. HTPC steps live under `periphery/`.

| Path | What |
|---|---|
| `core.sh` | Greenfield NAS bootstrap (OMV, Docker, Komodo Core, first Periphery) |
| `core/` | NAS host: static LAN, Docker engine, :53 bind, cage fan |
| `data-root/` | `DATA_ROOT` tree (prep before OpenCloud, layout after publish) |
| `omv/` | OMV NFS/SMB exports, IronWolf disk migrate, USB UPS (NUT) |
| `opencloud/` | Space adopt, PosixFS assimilate timer, readiness check |
| `komodo/` | Core compose template, secret ingest, Authelia OIDC seed |
| `periphery/` | HTPC Ethernet static LAN, Docker Desktop, NFS rebind, backup USB, Periphery compose |
| `first-run/` | Per-app first-run notes |
| `tools/` | One-off helpers (Vaultwarden JSON import) |
