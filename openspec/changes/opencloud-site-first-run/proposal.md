## Why

Bringing OpenCloud to a working household site required many one-off fixes (PosixFS layout, home/shared adopt, Collabora proof keys, Radicale ownership, OIDC roles, sticky layout dirs). A new site must follow one ordered path and a single health check instead of rediscovering those failures.

## What Changes

- Rewrite `bootstrap/opencloud.md` as a **happy-path first-run checklist** (secrets → deploy → adopt homes → adopt shared → perms → Collabora/Radicale smoke). Keep failure recovery in an appendix only.
- Add `bootstrap/opencloud-check.sh` that verifies containers, space xattrs, shared bind (inode equality), layout sticky/ownership, Radicale data ownership, and Collabora CA/proof readiness.
- Ensure `data-root-perms.sh` prepares OpenCloud host dirs (projects, radicale) for PUID before first Deploy so Docker does not leave root-owned binds.
- Document that `users/admin` is break-glass and that household adopt + sticky layout are required steps, not optional troubleshooting.
- Point README at the checklist.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `opencloud`: First-run SHALL be an ordered catalog procedure (adopt homes, adopt shared via parent projects bind + publish inode check, then `data-root-perms`); a check script SHALL report ready/not-ready.
- `collabora`: Site first-run SHALL treat Collabora CA bundle + proof_key volume and OpenCloud `COLLABORATION_APP_PROOF_DISABLE` as required for office editing (not optional recovery).

## Impact

- `bootstrap/opencloud.md`, new `bootstrap/opencloud-check.sh`, `bootstrap/data-root-perms.sh`, `README.md`
- OpenSpec deltas under this change for `opencloud` and `collabora`
- No compose behavior change required if catalog already has proof disable, projects parent bind, Radicale, and OIDC role mapping (verify and document only)
