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
3. On the remote host, follow `bootstrap/periphery.md`: Docker Desktop, map Core shares as `DATA_ROOT`, attach backup disk as `BACKUP_DRIVE`, start outbound Periphery with `PERIPHERY_CONNECT_AS=periphery`.
4. Confirm that server in Komodo, add `stacks/komodo/stacks-periphery.toml` to the same ResourceSync (or a second one), and apply.

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
