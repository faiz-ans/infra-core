# infra-core

Public, environment-agnostic app catalog for a two-host homelab. Site values (domain, IPs, disk paths, secrets, server names) live only in Komodo on-site. This git repo has compose files, config templates, and ResourceSync TOML.

## Layers

```
Layer 0  bootstrap/     OMV (optional), Docker, Komodo Core + local Periphery;
                        remote Docker engine + outbound Periphery
Layer 1  Komodo         Variables and secrets; polls git; no GitHub webhooks
Layer 2  this repo      stacks/ + windows/
```

Komodo server names in ResourceSync TOML are literals **`core`** and **`periphery`** (Komodo does not interpolate `[[VAR]]` on `server` or `repo`). Bootstrap `CORE_SERVER` / `PERIPHERY_SERVER` must match those names. Stack `repo` is this catalog (`faiz-ans/infra-core`). Environment values still use `[[VAR]]` at deploy.

## Bootstrap order

1. Copy `bootstrap/core.sh` plus `bootstrap/komodo/` to the Core host and run the script (or follow the commented commands). Storage is configured first; site prompts come after any OMV reboot.
2. In Komodo, confirm the `core` server. Secrets from bootstrap live in `/etc/komodo/core.config.toml`. Create a ResourceSync (webhooks off) with resource path `stacks/komodo/stacks-core.toml` first, then apply.
3. On Core, export DATA_ROOT over NFS (`bootstrap/omv-nfs.md`). Keep SMB for Explorer/Finder. On the remote host, follow `bootstrap/periphery.md`: Docker Desktop, Komodo `NAS_LAN_IP` + `NFS_EXPORT`, outbound Periphery with `PERIPHERY_CONNECT_AS=periphery`. Leave `restic` / `restic-rest` off until the IronWolf is the backup disk (`BACKUP_DRIVE`).
4. Confirm that server in Komodo, add `stacks/komodo/stacks-periphery.toml` to the same ResourceSync (or a second one), and apply. Home Assistant uses a local volume + git `configuration.yaml`; the other HTPC apps use NFS.

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
