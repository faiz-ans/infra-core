## Why

This repository still deploys one household: hardcoded host keys, `site.env`, `apply.sh`, OpenMediaVault, and chat-only lessons. It needs to become a site-agnostic product: a topology file in, push-based Ansible out, so any Debian/Ubuntu pair of storage and workload hosts can reach a working site without rewriting bootstrap scripts.

## What Changes

- **BREAKING:** Scrap the personal-site bootstrap (`core.sh`, `apply.sh`, `/etc/infra-core/site.env`, `MANIFEST.toml` host keys, Materia pull). The live repo MUST contain no household hostnames, IPs, user lists, or disk UUIDs. A local `site.yaml` is gitignored; git ships a schema and an empty/sample topology.
- **BREAKING:** Remove OpenMediaVault. NAS is OS-native mounts, Samba, and NFS. Cockpit is the UI when selected as host manager.
- Add OpenLDAP as an officially integrated site-level directory (must still be placed on a workload node).
- Sites are declared in `site.yaml`. Ansible on the operator’s machine generates inventory and runs **GET** / **SET**. Day 0 is GET facts. Day 1 is SET from desired topology. Day 2 diffs **desired** (`site.yaml`) against **observed** (GET output) and SET applies only the delta.
- Two host roles (storage, workload). Standalone scale only (native NAS + Podman). Cluster (Ceph / Kubernetes) is out of scope.
- Three logical data roots: `appdata`, `groups` (including `/all`), `users`. People use SMB (and OpenCloud when selected). Services use NFS only when the consumer is not on the owning host; the engine infers those exports.
- Site-level service keys (`networking.dns`, `identity.sso`, …) are policy, not deploy—except Cockpit on every host and Glances on every workload host. Elevated services must also appear under a workload node or SET errors.
- Official services are those already in `components/` plus OpenLDAP, minus OMV. Comment-only engines (Traefik, Authentik, Nextcloud, …) stay vocabulary. Forks/PRs may add integrations.
- Quadlet/pod YAML stays kube-play **Pod** format. Strip Kubernetes-only kinds and fields Podman does not need. `${site.*}`, `${host.*}`, and `${secrets.*}` resolve from topology and SOPS. Secrets are Age/SOPS on the runner and Podman secrets at runtime.
- SET never deletes user or group home data; it may delete accounts (unix/LDAP/SSO) only. Import blocks stay until the operator removes them after success; Caddy/Authelia imports land as `*.old`.
- Retain Windows/HTPC work outside GET/SET. Archive leftover bootstrap scripts and first-run novels. Encode already-learned deploy constraints in Ansible and catalog templates (lan-bind OUTPUT, OpenCloud OIDC, PeaNUT host-net, Homepage loopback tiles, WG MTU, keep-id/chown, xattrs).

## Capabilities

### New Capabilities

- `site-topology`: Desired `site.yaml` schema (roots, access, identity, networking, operations, env, site users, hosts as a list, roles, resources, imports, host identity/env/roots). Observed YAML is a separate GET artifact. Site-level vs instance placement rules.
- `ansible-control`: Push-based GET (facts vs site-influenced state), SET (idempotent apply), inventory generation from topology, desired-vs-observed diff on Day 2. Runner lives on the operator machine. Supported host OS: Debian and Ubuntu.
- `native-storage`: Native disk mount by UUID, root ownership, SMB for people, inferred NFS for cross-host services, create/move roots, import mapping, no OMV, no data-home deletion.
- `site-identity`: OpenLDAP (optional SoT), Authelia SSO, unix/SMB accounts on storage that owns `groups`/`users`, user roles (sysadmin/sysuser/appadmin/appuser), host-local sysadmins, SSH key-only gating. Account delete does not delete homes.
- `catalog-templates`: Official service pack, generated Caddy/Authelia (and related site-level config), topology variable resolution, SOPS → Podman secrets, Quadlet install, retained live-site lessons.

### Modified Capabilities

- `site-deploy`: Happy path becomes GET → edit desired → SET, not flash + `core.sh` + `apply.sh` phases.
- `gitops-catalog`: Public catalog is schema + example topology + Ansible + `components/`. No site identity in git. No Materia `MANIFEST.toml` as deploy source.
- `nas-bootstrap`: Layer 0 OMV/NUT/OMV-NFS scripts are replaced by native-storage SET. No OMV.
- `site-storage`: Roots are `appdata` / `groups` / `users`, not `system` / `shared` / `users`.
- `edge-access`: Ingress/DNS/lan-bind come from topology + catalog-templates, not a hardcoded Core Caddyfile.
- `quadlet-apply`: `apply.sh` envsubst is replaced by Ansible SET + catalog-templates resolution.
- `opencloud`: Spaces and binds use the new roots; xattrs and “do not recreate if present” remain; imports remap old trees.
- `homepage`: Tiles and scrape URLs come from topology + official pack (including host-loopback rules).
- `bootstrap-phases`: `core-bootstrap` / `core-full` roles are replaced by Day 0/1/2 GET/SET.
- `materia-gitops`: Pull-based Materia is not a deploy path.
- `materia-optional`: Optional Materia timer is removed; Ansible push is the only apply path.

## Impact

- Removes or archives `bootstrap/` scripts and first-run docs; `MANIFEST.toml` host/role lists; OMV helpers; live `site.env` contract.
- Adds `ansible/`, `schema/`, `examples/site.example.yaml`, gitignore for local `site.yaml` and Age keys.
- Reworks `components/` Quadlets (Pod YAML kept, K8s-only fields stripped, topology variables).
- Adds OpenLDAP component; removes OMV as a supported NAS.
- `windows/` and HTPC specs stay; they are not driven by GET/SET.
- Main specs listed above need deltas; per-app specs (Immich, Vaultwarden, …) inherit catalog-templates and do not each need a rewrite unless their SHALL text names OMV paths or `DATA_ROOT/system`.
