# Komodo ResourceSync catalog

## Topology (source of truth)

Edit [`topology.toml`](topology.toml) to assign each stack to a Komodo server, set `phase` (`bootstrap` or `full`), or omit a stack with `enabled = false`.

Stack bodies live in [`fragments/`](fragments/) (one `[[stack]]` file per name). Regenerate committed TOML:

```bash
python3 stacks/komodo/generate-stacks.py
```

| Output | Contents |
|---|---|
| `stacks-bootstrap.toml` | Phase A (may mix servers: e.g. OpenCloud on `core`, Collabora on `periphery`) |
| `stacks-core.toml` | Phase B stacks with `server = "core"` |
| `stacks-periphery.toml` | Phase B stacks with `server = "periphery"` |
| `stacks-<name>.toml` | Phase B for any additional server name |

Do **not** hand-edit the generated `stacks-*.toml` files; change topology or fragments, then regenerate.

Topology `linked_repo` is the Komodo Repo name ResourceSync Selects. Stacks clone GitHub themselves (`repo = "faiz-ans/infra-core"`). `select_repo = true` on a stack is opt-in Select Repo.

### This reference site

Servers remain **`core`** and **`periphery`** with the same placement as before, except phase-A stacks are carved into `stacks-bootstrap.toml`.

### Deferred

Multi-periphery **Caddy upstream** maps and **NFS** export assumptions for N data hosts are out of scope for `bootstrap-rewrite`. Extra server names may appear in topology later; networking vars stay single-`HTPC_UPSTREAM` until a follow-on change.

### Greenfield ResourceSync order

1. Apply **`stacks-bootstrap.toml`** only (after `data-root-prep.sh` and Authelia users).
2. Finish OpenCloud spaces + publish + `data-root-layout.sh` + OMV shares.
3. Apply **`stacks-core.toml`** and **`stacks-periphery.toml`** (or your generated per-server files).

### Existing site migration

Add a ResourceSync resource path for `stacks/komodo/stacks-bootstrap.toml` (same repo/poll settings). Phase-A stacks move out of the core/periphery files; running containers are not reshuffled by name. After sync, confirm bootstrap stacks still target the same servers, then Redeploy only if definitions drifted.

### Adding a stack later

1. Enable it in `topology.toml` (and set `deploy = true` in `fragments/<name>.toml` if it was cold).
2. `python3 stacks/komodo/generate-stacks.py`
3. On Core: `sudo bash bootstrap/sync-komodo-secrets.sh` (prompts/generates only **new** keys; no Komodo UI)
4. Recreate Komodo Core compose so `[secrets]` reload; Redeploy the new stack.
