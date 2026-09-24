## Context

`podman-rewrite` already chose the runtime: kube-play YAML + Quadlet `.kube` / `.container`, host names `core` / `surface` / `mantle`, split privilege, Cockpit on Core. That end state stays.

What failed is the **story** of how you get there. The catalog still assumes a live OMV with Docker/Komodo (purge, export named volumes) and treats Materia as Layer 0 (`materia update`, `.gotmpl`, `m_outputDir`). The first apply assumed Materia APIs that v0.7.2 does not implement. `core.sh` enables host REDIRECT of `:53`/`:80`/`:443` before Pi-hole or Caddy exist. A secret `while read` shares stdin with `prompt`.

This site will re-image the Pi OS disk and remount the IronWolf. Surface/mantle are not re-wiped. Materia is a convenience while this lab still iterates; future static sites will not run hundreds of git pulls, and their GitOps is undecided.

Constraints: do not wipe the data disk; do not restore Authelia sqlite; do not commit age keys or plaintext vaults; do not install mantle `*-full` while idle; do not make Materia the default bootstrap.

## Goals / Non-Goals

**Goals:**

- Layer 0 is empty OS + `core.sh` + remount-or-format-empty `DATA_ROOT` + Podman + Cockpit + on-box site env.
- Default stack install is a catalog apply script (roles, subst, Quadlets, systemd). No Materia binary, timer, or template functions required.
- Same OpenCloud-before-layout order as `bootstrap-rewrite`.
- Lan-bind and host DNS that depends on Pi-hole happen only after those ports listen.
- Docker-move scripts and docs are gone from the happy path.
- Operator runbook for this reflash (keep IronWolf, re-insert saved configs) and for a future empty disk.
- Optional Materia enablement that calls the same apply script.

**Non-Goals:**

- Changing the Podman/Quadlet/Cockpit/split-privilege target from `podman-rewrite`.
- Wiping the IronWolf or re-flashing Surface.
- Choosing GitOps for future static sites (Materia, FetchIT, ansible-pull, Argo, or none).
- Using Materia's renderer (`.gotmpl`, `m_dataDir`, `m_outputDir`) as the catalog source of truth.
- Running Kubernetes.
- Restoring Authelia sqlite after a rotated storage key.
- Implementing the physical flash in CI.

## Decisions

### 1. Default apply is Quadlets + site env; Materia is optional

Materia today does four jobs: pick host/role, decrypt age vaults, render `.gotmpl`, install systemd units. Only the last is the product. Default bootstrap MUST do role pick + subst + Quadlet install **without** Materia.

```
DEFAULT                         OPTIONAL (this lab)
───────                         ───────────────────
core.sh → Podman, Cockpit,      materia-enable.sh
          /etc/infra-core/      (binary + timer only)
          site.env
apply.sh --role *-bootstrap     timer: git pull && apply.sh
apply.sh --role *-full          MUST NOT render a parallel .gotmpl tree
```

Site values live in `/etc/infra-core/site.env` (mode 600, never git). Catalog Quadlets and kube YAML use `$DOMAIN`, `$DATA_ROOT`, `$SURFACE_UPSTREAM`, and similar placeholders substituted at apply time (or Quadlet `EnvironmentFile=` where that is enough). `.kube` `Yaml=` MUST point at a `pod.yaml` beside the unit after install (e.g. `/etc/containers/systemd/<app>/pod.yaml`), not `/var/lib/materia/...`.

`MANIFEST.toml` remains the **role list** (`core-bootstrap`, `core-full`, …). `apply.sh` reads it. It is not a promise Materia is installed. Committed default host roles are bootstrap-only; the operator adds `*-full` after gates.

**Alternative considered:** Keep Materia as Layer 0 and only fix `m_dataDir` / the install URL. Rejected: future sites should not expect a GitOps poller, and Materia's renderer was the Quadlet path bug class.
**Alternative considered:** Dual catalog (`.gotmpl` for Materia, envsubst for default). Rejected: two renderers will drift.
**Alternative considered:** Cron `git pull` as the default. Rejected: static sites do not need a poller in Layer 0; optional Materia (or a later GitOps choice) can wrap `apply.sh`.

### 2. From-scratch OS; data disk is remounted, never casually formatted

`core.sh` Layer 0:

1. apt / OMV (workbench `:81`) / NUT if needed (skip NUT apt when already installed; `omv-salt` must not abort the script if monit is down — start monit or continue).
2. If a `/srv/dev-disk-by-uuid-*` is already mounted, that is `DATA_ROOT`. If an extra disk already has ext4, mount/register it; do **not** offer format. Format only when there is no ext4 and the operator types `YES`.
3. Site secrets into `/etc/infra-core` (answers + `site.env`), static `NAS_LAN_IP`.
4. Podman (linger `pilot`), Cockpit, `podman.socket`. **Not** Materia.
5. `core-net` with **public** DNS (`1.1.1.1` / `8.8.8.8`) until Pi-hole exists.
6. Fan; `data-root-prep.sh` only.
7. Authelia `users.yml` / OIDC files **only if missing**.
8. Stop. Print: `apply.sh --role core-bootstrap`, then lan-bind after ports listen. Mention optional `materia-enable.sh` as a separate step.

`core.sh` MUST NOT: enable `core-lan-bind`, export NFS, mkdir the full protected `shared/{media,…}` tree, install Materia, or run a silent full-catalog apply.

**Alternative considered:** Keep “no re-flash” from `podman-rewrite`. Rejected: that path is the one-time Docker move we are abandoning.

### 3. Secret collection must not steal `prompt` stdin

`site-secrets.sh` MUST NOT `while read` from a process substitution that replaces the script’s stdin. Use a temp file, an array, or a dedicated FD. Rename `komodo_*` helpers to site/infra names. Drop `/etc/komodo` answer import. Write answers and `site.env` under `/etc/infra-core`.

### 4. Phased roles (not a Materia feature)

Committed default:

```
[Hosts.core]
Roles = ["core-bootstrap"]

[Hosts.mantle]
Roles = ["mantle-bootstrap"]
```

`core-bootstrap`: `site-network`, `caddy`, `authelia`, `pihole`, `glances`, `peanut`, `homepage`, `opencloud`. `mantle-bootstrap`: Collabora (+ site network). Operator adds `core-full` / `mantle-full` after OpenCloud/layout/NFS (Core) or Collabora (mantle).

WireGuard, Vaultwarden, and the rest of today’s `core-full` stay out of phase A.

### 5. Lan-bind is a gated operator step

Install the `core-lan-bind` unit **disabled**. Enable only when `:15353`, `:8080`, and `:8443` already listen. Then switch host resolved to `127.0.0.1:15353` with FallbackDNS that is **not** subject to the OUTPUT REDIRECT (or exclude host-to-self from the redirect). Until then, Core MUST resolve `github.com` via public DNS.

### 6. OpenCloud: two documented happy paths

**Empty disk:** prep → phase A → household Authelia login → create Project Space `shared` → publish → photos spaces → `data-root-layout.sh` → NFS → `*-full`.

**Existing data disk (this site):** remount → prep is mkdir `-p` → phase A → if `system/opencloud` + space xattrs exist, do **not** create spaces; verify `user.oc.space.*`; layout; NFS. Park/adopt only if config/data is corrupt and posix/users/shared are intact. Wipe at most `system/opencloud/{config,data}`.

`core.sh` MUST NOT call layout or NFS.

### 7. Purge Docker-move artifacts from the live tree

Remove or demote to an archive note (not README happy path):

| Artifact | Action |
|---|---|
| `bootstrap/core/purge-docker-komodo.sh` as a required `core.sh` step | delete or no-op; do not document as Layer 0 |
| `/etc/komodo` answer/state copy | delete |
| `komodo_*` function names | rename |
| README / `bootstrap/README.md` “export Docker volumes → purge” | replace with the reflash runbook |
| `bootstrap/omv/ironwolf-migrate.md` as default | keep only as lab history, not step 0 |
| `core-lan-static.sh` `/etc/komodo` paths | `/etc/infra-core` |
| first-run “Periphery” / `HTPC=periphery` leftovers | `mantle` / `SURFACE_UPSTREAM` |
| OpenCloud “existing site / whole shared/ was the space” as the primary checklist | appendix only |
| Materia install as required Layer 0 | move to optional `materia-enable.sh` |

Archived OpenSpec changes stay in `openspec/changes/` (history).

### 8. This-site config re-insert is restore, not conversion

After phase A, if the remounted tree is missing a saved file, unpack the off-box tarball:

- Caddy PKI → `${DATA_ROOT}/system/caddy`
- Authelia `users.yml` + `oidc.pem` + client secret files (not sqlite)
- Homepage YAML only if it differs from git `components/homepage/config/`
- Vaultwarden: use the live dir if present; import JSON only if empty

If optional Materia is enabled later, an age key from the laptop copy may be restored so existing `attributes/*.age` still decrypt. Default path does not need age.

### 9. Operator runbook lives in the catalog

One first-class doc (e.g. `bootstrap/SITE-DEPLOY.md` or rewrite of `bootstrap/README.md` + root README) with numbered parts: copy off-box → catalog-gate → flash OS only → remount and prove data → Layer 0 → phase A apply → restore configs → lan-bind → OpenCloud/layout/NFS → phase B → VW import-if-empty → optional Materia → mantle later. This site’s IPs/uuid stay out of git; the doc uses placeholders and points at `/etc/infra-core/site.env`.

## Risks / Trade-offs

- **[Operator formats the IronWolf]** → `core.sh` never formats an existing ext4; runbook mounts the uuid **before** `core.sh`; abort if `users/` / `shared/` / `system/vaultwarden` are missing.
- **[Two renderers if Materia is enabled carelessly]** → `materia-enable.sh` documents and implements “git pull && apply.sh” only; delete or stop using `.gotmpl` as source of truth.
- **[Host DNS dead after lan-bind]** → public DNS until listeners; FallbackDNS not REDIRECTed; `getent hosts github.com` is a gate.
- **[OpenCloud spaces lost]** → never wipe posix/users/shared; rsync/tar of those trees if taken must keep `-X` xattrs.
- **[Secret loop / garbled DOMAIN]** → answers file + stdin fix; `site.env` printed at end of Layer 0 for operator check.
- **[Phase B applied too early]** → committed `MANIFEST.toml` is bootstrap-only; docs say not to add `*-full` until layout/NFS (Core) or Collabora (mantle) is done.
- **[apply.sh is a one-shot, units drift from git]** → accepted for static sites; optional Materia (or a later GitOps choice) is the poller, not Layer 0.

## Migration Plan

1. Land this change on git (Quadlet subst, `apply.sh`, bootstrap split, docs, default roles). Do not flash on unpatched HEAD.
2. Operator already copied configs off-box (`~/core-reflash-backup`).
3. Flash OS media only; remount IronWolf; `core.sh`; `apply.sh --role core-bootstrap`; restore if needed; lan-bind; layout/NFS; `core-full`.
4. Optional: `materia-enable.sh` only if this lab still wants git-poll while iterating.
5. Mantle `*-full` when Core edge is boring.
6. Rollback of the **catalog** is revert this change. Rollback of a **flashed OS** is re-image again; data stays on the IronWolf. There is no Docker rollback path.

## Open Questions

- Exact runbook filename (`bootstrap/SITE-DEPLOY.md` vs folding into `bootstrap/README.md`) — pick during apply; one canonical entry from root `README.md`.
- Whether `glances` / `peanut` stay in `core-bootstrap` (current) or move to `core-full`. Default: keep them in bootstrap (UPS/metrics next to edge).
- Exact subst tool (`envsubst` vs a tiny Go/Python renderer). Default: `envsubst` from `site.env`; pick during apply if Quadlet files need a delimiter that conflicts with Caddy `{$VAR}`.
