## Why

New-site bootstrap still assumes a fixed two-host topology and creates household paths before OpenCloud can stamp PosixFS space xattrs, which forces park/restore. Site-agnostic installs need a declarative server split, a phase-A ResourceSync file, and a greenfield disk order that avoids park unless content already exists.

## What Changes

- Add a **declarative topology** file (servers, stack→server|exclude, phase, compose flavor) as the first step of bootstrap (step 0).
- Add a **generator** that emits committed ResourceSync TOML, including **`stacks-bootstrap.toml`** (phase A) and per-server phase-B files. **BREAKING** for operators who only know `stacks-core.toml` / `stacks-periphery.toml` as hand-edited sources of truth — those become generated outputs.
- Preserve **this site’s** Core/Periphery assignments aside from carving phase-A stacks into `stacks-bootstrap.toml`.
- Split host prep: **`data-root-prep.sh`** (system/, empty users/, OpenCloud host dirs) vs **`data-root-layout.sh`** (protected dirs + ACL/sticky after publish). Retain this site’s var defaults; do not blank them.
- Greenfield OpenCloud path: Authelia users → deploy phase A → login creates homes → create Space `shared` → publish bind → layout perms → OMV shares → phase B stacks. Keep adopt/park scripts as utilities.
- Homepage **seed** config for new sites; **do not** overwrite this site’s customized `stacks/platform/homepage/config/*`.
- Rewrite bootstrap docs / README for the two-phase flow; align `opencloud-check.sh` and related docs.
- **Out of scope:** multi-periphery Caddy upstream map and NFS rewiring for N data hosts (follow-on).

## Capabilities

### New Capabilities

- `site-topology`: Declarative server/stack assignment and generation of ResourceSync TOML (`stacks-bootstrap.toml` + per-server full-phase files).
- `bootstrap-phases`: Ordered greenfield bootstrap (prep → phase A → OpenCloud spaces → publish → layout → OMV → phase B), including split host-perm scripts and homepage seed.

### Modified Capabilities

- `opencloud`: First-run happy path is greenfield (no park by default); park/restore remains documented recovery.
- `gitops-catalog`: ResourceSync TOML is generated from topology; catalog remains site-agnostic for secrets/IPs/domains while topology declares stack placement.
- `nas-bootstrap`: Core bootstrap creates thin prep (`system/`, empty `users/`, OpenCloud dirs), not full household layout before OpenCloud; wires topology as step 0.

## Impact

- `stacks/komodo/` (topology + generator + `stacks-bootstrap.toml`; regenerate `stacks-core.toml` / `stacks-periphery.toml`)
- `bootstrap/` (`data-root-prep.sh`, `data-root-layout.sh`, `core.sh`, `opencloud.md`, README pointers, homepage seed)
- `stacks/platform/homepage/config.seed/` (or equivalent); existing `config/` unchanged
- Adopt scripts retained; `opencloud-check.sh` / docs updated
- Follow-on (not this change): N-periphery Caddy/NFS
