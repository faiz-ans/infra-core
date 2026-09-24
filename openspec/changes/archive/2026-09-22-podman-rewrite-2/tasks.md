## 1. Layer 0 without Materia

- [x] 1.1 Split Podman/Cockpit/linger/`podman.socket` out of `materia-install.sh` into a Layer 0 install that `core.sh` calls; stop installing Materia, timers, and `/etc/materia` from `core.sh`
- [x] 1.2 Move answers/`site.env` to `/etc/infra-core`; rename `komodo_*` helpers; drop `/etc/komodo` import; fix secret-list stdin so `prompt` cannot steal `DOMAIN`/`NAS_LAN_IP`
- [x] 1.3 `core.sh`: use a pre-mounted `/srv/dev-disk-by-uuid-*` as `DATA_ROOT`; never format an existing ext4; format only with typed `YES` on a disk with no ext4
- [x] 1.4 `core.sh`: public DNS only; do not enable `core-lan-bind`; do not export NFS; call `data-root-prep.sh` only (no protected `shared/` mkdir); skip NUT apt if present; start monit or continue on `omv-salt` failure
- [x] 1.5 Authelia `users.yml` / OIDC files only if missing; print next step as `apply.sh --role core-bootstrap` (optional Materia mentioned separately)

## 2. Default Quadlet apply

- [x] 2.1 Add `apply.sh` (or equivalent) that reads `MANIFEST.toml` roles, substitutes `/etc/infra-core/site.env`, installs system vs user Quadlets, `daemon-reload`s, and starts units without a Materia binary
- [x] 2.2 Set committed `[Hosts.core]` / `[Hosts.mantle]` to bootstrap roles only
- [x] 2.3 Replace `.gotmpl` / `m_outputDir` / `m_dataDir` in default components with subst-friendly Quadlets; `.kube` `Yaml=` MUST be a `pod.yaml` beside the unit after apply
- [x] 2.4 Fix OpenCloud catalog literals that used Sprig `quote`/`printf` so they survive the default renderer

## 3. Optional Materia

- [x] 3.1 Add `bootstrap/core/materia-enable.sh` (and mantle equivalent if needed): binary pin, age key, timer that `git pull`s and runs `apply.sh` only — no parallel `.gotmpl` render
- [x] 3.2 Document that Layer 0 MUST NOT call the enable script; future GitOps remains unspecified

## 4. Edge, storage, purge leftovers

- [x] 4.1 Install `core-lan-bind` disabled; document/enable only after `:15353`/`:8080`/`:8443`; host FallbackDNS must work after enable (`getent hosts github.com`)
- [x] 4.2 Keep `data-root-prep.sh` from creating `shared/media` (and other protected layout); layout + NFS stay operator steps after OpenCloud; document empty-disk vs remounted-disk OpenCloud paths
- [x] 4.3 Remove or demote Docker-move happy path: `purge-docker-komodo.sh` as required `core.sh` step, `/etc/komodo` paths in `core-lan-static.sh`, IronWolf USB migrate as step 0, Periphery/`HTPC=periphery` leftovers

## 5. Runbook and docs

- [x] 5.1 Write the canonical site-deploy runbook (copy off-box → flash OS only → remount/prove data → Layer 0 → phase A → restore configs → lan-bind → layout/NFS → phase B → VW if empty → optional Materia → mantle later); point root README at it; no Docker export/purge
- [x] 5.2 Rewrite `bootstrap/README.md` and first-run entry docs for `apply.sh` (not `materia update`); Authelia sqlite restore is not a step

## 6. Verify

- [x] 6.1 `openspec validate --change podman-rewrite-2` (or equivalent)
- [x] 6.2 Grep that default catalog/bootstrap does not require `materia update`, `m_outputDir`, or `/etc/komodo` on the happy path
- [x] 6.3 Confirm `MANIFEST.toml` host roles are bootstrap-only and no live IPs/domains/secrets in `components/`
