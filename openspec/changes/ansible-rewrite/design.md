## Context

The repo today is a household GitOps catalog: `MANIFEST.toml` names `core`/`mantle`, `bootstrap/apply.sh` envsubst’s `/etc/infra-core/site.env`, Quadlets land via systemd, NAS is OpenMediaVault, identity is Authelia file-backend, and deploy lessons live in first-run markdown. Phase A on this site works. The product goal is that **any** Debian/Ubuntu storage+workload site can do the same from a topology file, without this house’s names in git.

Constraints carried in: on-prem only; standalone scale (native NAS + Podman); cluster out of scope; push-based Ansible from the operator machine; retain Windows/HTPC outside this loop; keep kube-play **Pod** YAML; strip Kubernetes-only fields; desired and observed are **two files**; SET may delete accounts, never homes.

## Goals / Non-Goals

**Goals:**

- Site-agnostic git catalog: schema, example topology, Ansible, official `components/`.
- Day 0 GET facts → Day 1 SET desired → Day 2 diff(desired, observed) → SET delta.
- Native NAS (mount, Samba, inferred NFS). Cockpit as optional host UI.
- OpenLDAP optional SoT; Authelia SSO; unix/SMB on storage that owns `groups`/`users`.
- Official service pack encodes ports, SSO mode, tiles, host-net vs site, and already-learned failure modes.
- Topology variable resolution (`${site.*}`, `${host.*}`, `${secrets.*}`) and SOPS → Podman secrets.
- Archive obsolete bootstrap scripts/docs. Keep `windows/`.

**Non-Goals:**

- Ceph, LVM pooling, Kubernetes, Ansible-pull, Materia.
- OMV, Traefik, Authentik, Keycloak, Nextcloud, AdGuard, Tailscale as implementations.
- Driving Windows `surface` through GET/SET.
- Deleting user/group home data on account removal.
- Rewriting Pod YAML into `.container` files except where a unit is already a single Quadlet.

## Decisions

### 1. Desired and observed are separate files

- **Desired:** operator-owned `site.yaml` (gitignored locally; `examples/site.example.yaml` in git).
- **Observed:** GET writes `observed.yaml` (gitignored). GET never writes desired.
- Day 0 GET (Task A only) can **print a scaffold** the operator copies into a new `site.yaml` (IPs + discovered hostname/mac/os/disks/users). That scaffold is a convenience, not a merge into an existing desired file.
- Day 2 GET runs A+B and overwrites observed only. Diff is `desired − observed` (plus implicit Glances/Cockpit).
- **Alternative:** one merged file. Rejected: GET would clobber `roles`, `import`, PWM `scale`, and `users`.

### 2. Inventory is generated, hosts are a list

`site.hosts` is a list of objects (`name`, `ip`, `…`). Ansible inventory maps `name → ansible_host=ip`, `ansible_user` from the host’s sysadmin (or Day 0 CLI: IP + admin user). IPs and hostnames are never schema keys.

### 3. GET tasks

| Task | When | Collects |
|---|---|---|
| A | Day 0 and Day 2 | hostname, mac, OS+version, timezone, locale, `lsblk` (scaffold lists data partitions under a disk, or `name`/`size`/`uuid` on the disk when it has none; disks with no filesystem UUID are omitted), `lspci`/`nvidia-smi` NVIDIA GPUs on the site host (not Microsoft Basic Render; nvidia-smi may be off PATH under `/usr/lib`), `/sys/bus/usb` + `lsusb` plug-in USB peripherals (not root hubs, hub chips, or USB-ethernet), PWM hwmon path, unix users uid>1000 (name/uid/gid) |
| B | Day 2 (and optional Day 1 verify) | `findmnt`, NFS/SMB exports, Cockpit/Podman present, deployed containers, LDAP joined + directory identifiers if LDAP is up |

Day 0 input is the minimum needed to SSH: host IPs and admin usernames.

### 4. SET order (internal graph)

SET is one playbook, ordered:

1. Host facts / OS family (Debian vs Ubuntu packages)
2. Disks: mount by UUID; create/move roots; run `import` once (stamp in observed / marker file under the dest)
3. Host-local sysadmins and SSH keys; refuse `identity.ssh: key-only` if no sysadmin key is present
4. Site users/groups on storage that owns `groups`/`users` (unix or SSSD)
5. Site-level directory (OpenLDAP) if placed; join storage to LDAP
6. Resource drivers (NVIDIA, NUT if a USB device has `type: ups` — not PeaNUT)
7. PWM enable; apply `scale` only if the operator wrote it
8. Cockpit (every host if `operations.host.manager: cockpit`)
9. Podman + `site` network + linger for workload user
10. Secrets: decrypt on runner, `podman secret` on target
11. Inferred NFS exports (owner host) and mounts (consumer host)
12. Generate Caddy/Authelia/Homepage (and lan-bind) from topology + official pack
13. Install/remove Quadlets for listed services (plus implicit Glances on workload hosts)
14. OpenCloud xattr/bind steps when OpenCloud is placed; do not recreate spaces if xattrs exist

Remove means: stop unit, uninstall package/Quadlet, drop NFS export if unused. **Do not** `rm` homes or group directories.

### 5. Site-level keys vs instances

Elevated keys (`networking.dns`, `identity.sso`, `data.access.web`, `operations.storage.monitor`, `operations.workload.engine`, …) are policy. SET errors if the engine is not `none` and no workload lists that service — except:

- `operations.host.manager: cockpit` → install Cockpit on **every** host (not a container).
- `operations.host.monitor: glances` → deploy Glances on **every workload** host even if omitted from `services`. Next GET B may write it into observed.

OpenLDAP has **no** implicit placement: `identity.ldap: openldap` without a workload entry is an error.

A USB device with `type: ups` enables NUT only. PeaNUT requires an explicit service entry. GET records plug-in USB peripherals only (not root hubs, hub chips, or USB-ethernet NICs); the operator labels the UPS.

### 6. Roots, SMB, inferred NFS

Logical roots default to `/appdata`, `/groups`, `/users`. Each root is owned by exactly one storage drive on one host (`roles.storage.drives[].roots`). A host root listed on that same volume may use the site root's absolute path; SET keeps the one bind. The name does not select the share, and `${host.data.roots.*}` resolves only from `hosts[].data.roots`.

- People: SMB (and OpenCloud when `data.access.web: opencloud`) on user-homes and group-homes (`groups/<group>`, including `all`).
- Apps: if `${site.data.roots.*}` resolves to a root **on another host**, SET creates an NFS export to **that consumer host IP** as the workload UID (`roles.workload.user`). Same host → local path, no export.
- Unused inferred exports are removed on Day 2 SET.
- Service-specific dirs (`downloads`, `cameras`, …) are created only when an official service that needs them is desired.
- NFS writers use the workload UID; SET applies ACL/sticky so SMB and OpenCloud can manage those files. OpenCloud posix-scan remains when OpenCloud is placed.

### 7. Identity and deletion

| `identity.ldap` | Unix/SMB SoT | Authelia | GET identifiers |
|---|---|---|---|
| `openldap` (placed) | LDAP via SSSD on storage owning groups/users | LDAP backend | LDAP unique ids |
| `none` | Local unix on those storage hosts | File backend | unix uid/gid |

Roles: `sysadmin` (sudo+ssh, host-local list), `sysuser` (no sudo/ssh), `appadmin` / `appuser` (SSO). Site users get a home and SMB. Each unique `users[].groups` gets a group-home and SMB for members.

Removing a site user from desired SET **deletes the account** (unix and/or LDAP and SSO). Homes and group directories stay on disk.

### 8. Imports

`hosts[].resources.disks[].import` is a typed list. `from:` is relative to that disk’s systemd mount (`/` for `internal: true`, otherwise `/mnt/site/<id>`). Root types merge into `site.data.roots.*`; home types land under the matching root (`as:` / `to:` relocates). SET mounts each UUID once and bind-mounts sibling root dirs; it applies root-owning hosts first and uses a temporary NFS export of dest roots for cross-host imports. Success is stamped. Operator deletes the block after success. Generated files (Caddyfile, Authelia config) import as `*.old`.

### 9. Catalog templates and variables

Quadlets stay Pod YAML (plus existing `.container` / `.network` where already one process). Remove Ingress/Service/HPA and other kube-play-unused fields.

Resolution at SET on the runner:

- `${site.env.domain}`, `${site.data.roots.users}`, …
- `${site.networking.ingress.host.ip}` → IP of the unique host that lists the ingress engine. Two placements → error.
- `${host.resources.gpu.<id>.resource}` → kube-play limits key (`nvidia.com/gpu`); pods write the count literally (`${host.resources.gpu.gpu0.resource}: 1`). `id` is `gpu<index>` from `nvidia-smi -L`.
- `${secrets.site.<service>.<name>}`, `${secrets.<service>.<name>}`, and `${secrets.<name>}` are one site secret. `${secrets.hosts.<hostname>.<service>.<name>}`, `${secrets.host.<service>.<name>}`, and `${secrets.host.<name>}` are one host secret. `host` is the instance's host. A bare secret name uses the service being rendered. The Podman name of a service's own secret is `<service>_<name>` with hyphens removed from the service (`pihole_web_password`). A unit that reads another service's host secret is `<unit>_<service>_<name>` (`homepage_pi-hole_web_password`). A unit that reads another host's secret also includes that host (`homepage_mantle_pi-hole_web_password`). SET installs site secrets on every workload host, a host's own secrets on that host, and these cross-references on the unit's host.

Official pack (in-scope = current `components/` plus OpenLDAP, minus OMV) stores: default subdomains, ports, OIDC vs forward-auth, tile/monitor defaults, network mode, rootful vs rootless, and encoded lessons (Caddy keep-id + PKI chown; Authelia keep-id + oidc.pem chown; lan-bind PREROUTING plus OUTPUT `127.0.0.1:443→8443` and not OUTPUT `:53`; OpenCloud `PROXY_OIDC_ACCESS_TOKEN_VERIFY_METHOD=none`, autoprovision, `auth.` → pasta loopback `169.254.1.2`; Homepage `HOMEPAGE_ALLOWED_HOSTS` includes `:8443`, host scrapes via `169.254.1.2`, Pi-hole key = web password; PeaNUT host-net `:8092`, NUT `127.0.0.1`, no `AUTH_URL`; WireGuard MTU 1280; no space recreate if xattrs exist; `catatonit` / netavark helper path).

Comment-only engines in the example YAML are not implemented.

### 10. Secrets

Age key lives on the operator machine only. Encrypted SOPS files may live beside local `site.yaml` (gitignored) or an optional encrypted vault the operator chooses. The file nests site secrets under `secrets.site` and per-host secrets under `secrets.hosts.<name>`. SET decrypts in memory and pushes Podman secrets. No `/etc/infra-core/site.env` on hosts.

### 11. Repo layout

```
ansible/           playbooks get/set, roles, inventory templates
schema/            site.schema.json
examples/          site.example.yaml (no live IPs/UUIDs/users)
components/        official Quadlets + pack metadata
windows/           retained, not GET/SET
archive/           old bootstrap/, first-run novels, OMV helpers
site.yaml          gitignored (operator desired)
observed.yaml      gitignored (GET)
```

`.gitignore` covers `site.yaml`, `observed.yaml`, Age private keys, decrypted secrets.

### 12. OS and PWM

SET uses Debian vs Ubuntu package names from gathered `os.name`. PWM: GET A records the hwmon path. SET starts a fan loop only when `resources.pwm.enabled` is true and `scale` is set. `scale.steps` is the fan-duty list. Each of `sources.cpu`, `sources.disks.<id>`, and `sources.gpus.<id>` is a temperature-ceiling list of the same length. Duty is the highest step any reporting source demands (linear between ceilings, held 2 °C on the way down), clamped to `min`/`max`.

### Alternatives considered

- **Materia / ansible-pull:** rejected; this change is push-only from the dev machine.
- **Keep OMV:** rejected; native mounts + Samba + NFS + Cockpit.
- **Single topology file:** rejected (decision 1).
- **Rewrite all units to `.container`:** rejected; keep Pod YAML, strip unused K8s fields.

## Risks / Trade-offs

- **[Day 1 SET is large]** → Internal graph (decision 4). Operator can desired-list a small first SET (storage + identity + ingress) then add services.
- **[Inferred NFS + OpenCloud/SMB ownership]** → ACL/sticky + posix-scan when OpenCloud is placed; export only to consumer IPs.
- **[key-only SSH lockout]** → SET refuses key-only until a host sysadmin has a key.
- **[GET scaffold vs desired]** → Scaffold is opt-in copy; never overwrite existing `site.yaml`.
- **[Import re-run]** → Stamp after success; operator still removes the block.
- **[Two Caddy instances]** → Schema/SET error, not a guess.
- **[Leftover household identity in git]** → Catalog scan in CI or `ansible` check task; example YAML uses placeholders.

## Migration Plan

1. Land product tree (`ansible/`, schema, example) beside current catalog.
2. Archive `bootstrap/` scripts and first-run docs that SET replaces; keep `windows/`.
3. Strip site identity from committed Quadlets; switch variables to topology namespaces.
4. Operator: Day 0 GET A against live hosts → write local `site.yaml` (including IronWolf `import`) → SET.
5. Rollback: archive still contains the last `apply.sh` tree until the operator confirms SET. Do not wipe data disks. Account delete does not remove homes, so a bad user edit is reversible by re-adding the account.

## Open Questions

- Exact on-disk path for SOPS files on the runner (convention only: beside `site.yaml`).
- Whether Cockpit file-sharing plugin is enough to “see” native Samba, or SET also writes Cockpit config snippets.
- PWM named-header alias list per board (GET A can leave a raw hwmon path).
