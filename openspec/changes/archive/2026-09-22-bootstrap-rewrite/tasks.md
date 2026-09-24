## 1. Topology and generator

- [x] 1.1 Add declarative topology file for this site (`core` / `periphery`) matching current stack placement + phase `bootstrap` vs `full`
- [x] 1.2 Implement generator that emits `stacks-bootstrap.toml` and per-server phase-full TOML (preserve compose.yaml vs compose.nfs.yaml, unique stack names, `after`, env blocks)
- [x] 1.3 Generate committed TOMLs; diff-check non-bootstrap assignments unchanged aside from carve-out into `stacks-bootstrap.toml`
- [x] 1.4 Document topology edit → regenerate; note deferred multi-periphery Caddy/NFS

## 2. Host prep / layout split

- [x] 2.1 Split `data-root-perms.sh` into `data-root-prep.sh` and `data-root-layout.sh` (shared defaults retain this site’s DATA_ROOT / HOUSEHOLD / ADMIN / groups)
- [x] 2.2 Wire `core.sh` / docs to call prep early; layout only after OpenCloud publish
- [x] 2.3 Leave adopt-homes / adopt-shared park scripts as utilities; point greenfield docs away from park-by-default

## 3. Homepage seed

- [x] 3.1 Add minimal Homepage `config.seed/` (Komodo, OMV, Authelia, Pi-hole, OpenCloud links)
- [x] 3.2 Document new-site copy seed → `config/`; do not modify existing `config/*`

## 4. Docs and verification

- [x] 4.1 Rewrite `bootstrap/opencloud.md` and README for greenfield two-phase ResourceSync (`stacks-bootstrap.toml` then full TOMLs)
- [x] 4.2 Update `omv-nfs.md` / related bootstrap notes for shares after layout
- [x] 4.3 Align `opencloud-check.sh` messaging with greenfield + prep/layout script names

## 5. This site migration notes

- [x] 5.1 Add short migration note: add ResourceSync path for `stacks-bootstrap.toml` without reshuffling running non-bootstrap stacks
