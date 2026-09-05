## 1. Docs

- [x] 1.1 Rewrite `bootstrap/opencloud.md` as ordered happy-path first-run; move recovery to appendix
- [x] 1.2 Point `README.md` at the first-run checklist (Collabora + Radicale + adopt + check)

## 2. Host prep and check

- [x] 2.1 Ensure `data-root-perms.sh` creates and PUID-owns `projects/` and `radicale/` before sticky protect
- [x] 2.2 Add `bootstrap/opencloud-check.sh` (pass/fail: containers, spaces, shared inode, sticky, radicale, proof disable)
- [x] 2.3 Reference the check script at the end of the happy path in `opencloud.md`

## 3. Verify catalog already encodes hard-won settings

- [x] 3.1 Confirm opencloud compose has projects parent bind, OIDC roles, `COLLABORATION_APP_PROOF_DISABLE`, Radicale; note any gap in the doc only
