## Context

OpenCloud on Core is working after iterative fixes: PosixFS parent binds, home/shared adopt scripts, Collabora proof disable + CA sidecar, Radicale ownership, OIDC role mapping, and sticky layout dirs. `bootstrap/opencloud.md` still reads as a troubleshooting narrative. New sites need the same end state without that path.

## Goals / Non-Goals

**Goals:**

- One ordered first-run checklist a human can follow after `core.sh` / Deploy.
- One `opencloud-check.sh` that prints pass/fail for the known failure modes.
- Host dirs (projects, radicale) prepared before first container start where possible.

**Non-Goals:**

- Fully unattended adopt (browser login + create Space `shared` still required).
- Changing PosixFS/Collabora architecture already in compose.
- Automating Immich External Libraries (separate `immich.md`).

## Decisions

1. **Checklist doc over more Komodo automation** — Browser steps (OIDC login, create Space) cannot run in ResourceSync. Keep scripts for park/publish/restore/perms/check; document the human gates clearly.
2. **Inode equality for shared publish** — Already in `opencloud-adopt-shared.sh`; check script MUST use the same test (never `findmnt` alone).
3. **`data-root-perms` prepares radicale + projects** — `mkdir` + `chown PUID` before Deploy avoids root-owned binds; sticky protect still runs after adopt restore.
4. **Check script is read-only** — Diagnose only; never mount or chown (operator runs the named fix scripts).

## Risks / Trade-offs

- **[Human skips create Space `shared`]** → check fails with clear “no space id”; publish refuses.
- **[check run before perms after restore]** → sticky/ownership fails until `data-root-perms.sh`.
- **[chown -R system/opencloud while shared bind is live]** → can briefly set space root to PUID; protect_shared_layout after must remain last in `data-root-perms`.

## Migration Plan

Existing working sites: optional — run `opencloud-check.sh` for confidence; re-run `data-root-perms.sh` only if check fails sticky/ownership. No Redeploy required for docs/scripts alone.

## Open Questions

None — compose already contains Collabora proof disable and projects parent bind.
