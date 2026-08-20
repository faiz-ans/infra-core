# infra-core

Public, environment-agnostic app catalog for a two-host homelab. Site values (domain, IPs, disk paths, secrets, server names) live only in Komodo on-site. This git repo has compose files, config templates, and ResourceSync TOML.

## Layers

```
Layer 0  bootstrap/     OMV (optional), Docker, Komodo Core + local Periphery;
                        remote Docker engine + outbound Periphery
Layer 1  Komodo         Variables and secrets; polls git; no GitHub webhooks
Layer 2  this repo      stacks/ + windows/
```

Komodo server names default to **`core`** (this host: Core + local Periphery) and **`periphery`** (remote engine). ResourceSync uses `[[CORE_SERVER]]` and `[[PERIPHERY_SERVER]]`, so a given site can still choose names like `nas` / `htpc` at bootstrap.

## Bootstrap order

1. Copy `bootstrap/core.sh` plus `bootstrap/komodo/` to the Core host and run the script (or follow the commented commands). Storage is configured first; site prompts come after any OMV reboot.
2. In Komodo, confirm the `core` server (or your `CORE_SERVER` override), variables from `stacks/komodo/VARIABLES.md`, and ResourceSync on `stacks/komodo` (webhooks off). Apply the Core sync (`stacks-core.toml`).
3. On the remote host, follow `bootstrap/periphery.md`: Docker Desktop, map Core shares as `DATA_ROOT`, attach backup disk as `BACKUP_DRIVE`, start outbound Periphery with `PERIPHERY_CONNECT_AS` matching `PERIPHERY_SERVER`.
4. Confirm that server in Komodo and apply the Periphery ResourceSync (`stacks-periphery.toml`).

Winget packages for later Windows apps are listed under `windows/` and are not required for GitOps.

## Variable keys

See [`stacks/komodo/VARIABLES.md`](stacks/komodo/VARIABLES.md). Do not put values in this repository.
