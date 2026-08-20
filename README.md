# infra-core

Public, environment-agnostic app catalog for a two-host homelab. Site values (domain, IPs, disk paths, secrets) live only in Komodo on-site. This git repo has compose files, config templates, and ResourceSync TOML.

## Layers

```
Layer 0  bootstrap/     OMV, Docker, Komodo Core + first Periphery (Pi);
                        Docker Desktop + outbound Periphery (HTPC)
Layer 1  Komodo         Variables and secrets; polls git; no GitHub webhooks
Layer 2  this repo      stacks/ + windows/
```

Komodo server names: **`nas`** (Raspberry Pi) and **`htpc`** (Windows Docker Desktop). Those names are topology, not DNS.

## Bootstrap order

1. Copy `bootstrap/nas.sh` to the Pi (`scp`) and run it (or follow the commented commands inside). It prompts and writes secrets on the box.
2. In Komodo, confirm server `nas`, variables from `stacks/komodo/VARIABLES.md`, and ResourceSync on `stacks/komodo` (webhooks off). Apply the NAS sync.
3. On the HTPC, follow `bootstrap/htpc.md`: Docker Desktop, map OMV shares as `DATA_ROOT`, attach the USB as `BACKUP_DRIVE`, start outbound Periphery.
4. Confirm server `htpc` in Komodo and apply the HTPC ResourceSync.

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
