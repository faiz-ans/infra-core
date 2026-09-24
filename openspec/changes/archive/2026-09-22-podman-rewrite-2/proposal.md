## Why

`podman-rewrite` chose the right runtime (Podman Quadlets, kube-play YAML, `core` / `surface` / `mantle`) but the wrong first-run story: in-place Docker/Komodo purge on a live OMV, with Materia as the only way Quadlets land. That mix is un-debuggable, and Materia is a lab convenience while this site is still changing — not the default for a future static site. This change makes the catalog a from-scratch OS deploy, keeps the IronWolf, and takes Materia off Layer 0.

## What Changes

- **BREAKING:** Layer 0 is empty Pi OS + OMV + Podman + Cockpit + on-box `site.env`. It MUST NOT install Materia, MUST NOT purge Docker/Komodo as a required step, and MUST NOT treat `materia update` as the way stacks start.
- **BREAKING:** Default apply is a catalog script that substitutes site values and installs Quadlets into systemd (phase `core-bootstrap` / `mantle-bootstrap` first, then `*-full`). Quadlets MUST NOT require Materia template functions (`m_outputDir`, `m_dataDir`, `.gotmpl` as the only source).
- Materia is an **optional** add-on for this lab. If enabled, it MUST git-pull and invoke the same apply script — not a second renderer. How future static sites do GitOps is **out of scope**.
- Bootstrap order matches `bootstrap-rewrite`: prep → baseline edge + OpenCloud → OpenCloud spaces (or verify existing xattrs) → layout → NFS → lan-bind only after Pi-hole/Caddy listen → then `*-full`.
- This site’s exceptions: do not wipe the IronWolf; remount it; re-insert saved Vaultwarden / Caddy PKI / Authelia file-backend / Homepage layouts rather than generating them empty.
- Purge Docker-move leftovers from the live tree (`purge-docker-komodo.sh` as Layer 0, `/etc/komodo` imports, “export Docker volumes” README, IronWolf USB migrate as the happy path).
- Patch first-run bugs that would recur without Docker: secret-loop stdin, lan-bind before listeners, host DNS, `core.sh` creating protected `shared/` too early, NFS before layout, `komodo_*` names.

## Capabilities

### New Capabilities

- `site-deploy`: Operator runbook for from-scratch OS (and this site’s remount + restore exceptions). Phased apply. No Docker-cutover story.
- `nas-bootstrap`: Layer 0 on a new OS: OMV, remount-or-format-empty `DATA_ROOT`, Podman, Cockpit, `site.env`. No Materia. No required Docker purge.
- `quadlet-apply`: Default install of kube-play YAML + Quadlets from role lists using on-box site values. No Materia APIs in the default catalog.
- `materia-optional`: Optional enablement that wraps the same apply path. Not Layer 0. Future GitOps unset.
- `site-storage`: Prep before OpenCloud; layout after spaces; existing-disk vs empty-disk OpenCloud paths.
- `edge-access`: Host REDIRECT of `:53`/`:80`/`:443` only after Pi-hole and Caddy listen; host DNS must survive.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs; `podman-rewrite` deltas were never archived)

## Impact

- Repo: `bootstrap/core.sh` and install scripts, Quadlet/templates under `components/`, `MANIFEST.toml` as role data, README / first-run / OpenCloud docs. Optional `bootstrap/core/materia-enable.sh`.
- Core: re-image OS disk only; IronWolf remounted; household services return via `apply.sh`, not `materia update`.
- Surface/mantle: unchanged identities; mantle stacks still idle until Core baseline is up; no Windows re-wipe.
- External: catalog git remote stays the operator’s (this site: GitHub). No webhook requirement. No on-box forge.
- Out of scope: choosing GitOps for future static sites; Kubernetes; FetchIT/ansible-pull as replacements; wiping the IronWolf; restoring Authelia sqlite; flashing Surface.
