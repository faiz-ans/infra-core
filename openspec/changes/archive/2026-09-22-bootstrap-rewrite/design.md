## Context

The catalog hard-codes a two-host ResourceSync layout (`stacks-core.toml` / `stacks-periphery.toml`) and creates full household trees before OpenCloud can mkdir space roots. Greenfield sites and non–two-host topologies need topology-as-data, generated TOML, and a two-phase bootstrap that lets OpenCloud stamp xattrs before protected layout dirs exist.

## Goals / Non-Goals

**Goals:**

- Declarative topology as bootstrap step 0.0; generator emits committed ResourceSync TOML.
- `stacks-bootstrap.toml` for phase A (may mix `server` literals).
- Greenfield OpenCloud order without park; park scripts remain utilities.
- Split `data-root-prep.sh` / `data-root-layout.sh`; homepage seed without clobbering this site’s config.
- Preserve this site’s Core/Periphery stack placement aside from the bootstrap carve-out.

**Non-Goals:**

- Multi-periphery Caddy upstream map or NFS export redesign for N data hosts.
- Fully unattended OpenCloud (browser login + create Space `shared` still required).
- Changing live Authelia users or this site’s Homepage `config/*` content.

## Decisions

1. **Topology YAML in git is source of truth; TOML is generated and committed** — ResourceSync keeps clone-and-sync; operators edit topology then regenerate. Hand-editing generated TOML is unsupported (drift).
2. **This site’s topology encodes current `core` / `periphery` assignments** — Generator output matches today’s behavior plus phase-A extraction into `stacks-bootstrap.toml`.
3. **`stacks-bootstrap.toml` may contain mixed `server =` values** — One ResourceSync apply for phase A (e.g. OpenCloud on core, Collabora on periphery).
4. **Phase-B files remain per primary server name** — e.g. `stacks-core.toml`, `stacks-periphery.toml` (extendable to more server names later without Caddy/NFS rewrite in this change).
5. **Split scripts, not flags** — `data-root-prep.sh` vs `data-root-layout.sh`; shared defaults snippet may hold this site’s `DATA_ROOT` / `HOUSEHOLD` values.
6. **Homepage seed alongside live config** — e.g. `config.seed/`; new sites copy seed → `config/` once; existing `config/` unchanged.
7. **Protected dirs after publish** — mkdir children under OpenCloud-created space roots (or bound `shared/`); then ACL/sticky; optional `posixfs scan`.
8. **Narrow multi-host** — Schema allows N periphery names and `enabled: false`; Caddy/NFS multi-upstream deferred.

## Risks / Trade-offs

- **[Generated TOML drift]** → Document “edit topology, regenerate”; optional CI check that committed TOML matches generator.
- **[Existing site ResourceSync paths]** → Operators must add `stacks-bootstrap.toml` (or replace sync sources); document migration for this lab.
- **[Early layout script run]** → Recreates park need; docs + check script detect parked/missing space ids.
- **[Single-server sites]** — All stacks on `core`, compose bind; generator must not require a periphery server.

## Migration Plan

1. Add topology matching current split; generate TOMLs; verify diff vs hand-written (bootstrap carve-out only).
2. This site: add ResourceSync path for `stacks-bootstrap.toml` if phase-A stacks move out of `stacks-core.toml` / periphery file; Redeploy unchanged for already-running stacks.
3. New sites: step 0 topology → prep → phase A only → OpenCloud adopt-less path → layout → OMV → phase B TOMLs.
4. Rollback: revert commit; point ResourceSync at previous TOML paths.

## Open Questions

None for narrow scope — multi-periphery networking explicitly deferred.
