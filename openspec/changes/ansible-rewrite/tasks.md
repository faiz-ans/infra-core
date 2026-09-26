## 1. Product skeleton

- [x] 1.1 Add `schema/site.schema.json` for desired topology (list hosts, roots, identity, networking, operations, users, imports, overrides)
- [x] 1.2 Add `examples/site.example.yaml` with placeholders only (no live IPs, UUIDs, people, or this lab’s domain)
- [x] 1.3 Gitignore local `site.yaml`, `observed.yaml`, Age private keys, and decrypted secret files
- [x] 1.4 Add `ansible/` layout: `playbooks/get.yml`, `playbooks/set.yml`, `inventory/` generator, `roles/`
- [x] 1.5 Rewrite root README to Day 0 GET → edit desired → Day 1 SET → Day 2 diff (no `core.sh` / `apply.sh`)

## 2. GET

- [x] 2.1 Day 0 entry: IPs + admin usernames → SSH inventory
- [x] 2.2 Task A: hostname, MAC, OS+version, timezone, locale, lsblk, GPUs, UPS, PWM path, uid>1000 users
- [x] 2.3 Task B: findmnt, exports, Cockpit/Podman, containers, LDAP join + identifiers
- [x] 2.4 Write `observed.yaml` only; optional print scaffold for a new desired file; never overwrite existing desired
- [x] 2.5 Fail GET/SET with an explicit error on OS other than Debian or Ubuntu

## 3. Native storage and identity

- [x] 3.1 SET: mount disks by UUID; create/move `appdata`, `groups`, `users`; never format existing ext4
- [x] 3.2 SET: Samba user-homes and group-homes (including `groups/all`); no OMV packages
- [x] 3.3 SET: infer NFS export+mount when `${site.data.roots.*}` is consumed off-owner; same-host stays local; drop unused exports
- [x] 3.4 SET: service-specific dirs only when that official service is desired
- [x] 3.5 Import blocks: remap trees, stamp success, write Caddy/Authelia imports as `*.old`; do not re-copy
- [x] 3.6 Site users/groups: unix or OpenLDAP+SSSD on storage that owns groups/users; Authelia LDAP vs file backend
- [x] 3.7 Host sysadmins + SSH keys; refuse `key-only` until a key exists
- [x] 3.8 Account delete without deleting homes or group directories
- [x] 3.9 Add OpenLDAP official component; error if `identity.ldap: openldap` is not placed

## 4. Catalog templates and Quadlets

- [x] 4.1 Official pack metadata (subdomains, ports, OIDC vs forward-auth, tile/monitor, network mode) for current `components/` plus OpenLDAP
- [x] 4.2 Resolver for `${site.*}`, `${host.*}`, `${secrets.*}`; ingress host IP unique-or-error
- [x] 4.3 SOPS/Age on the runner → Podman secrets; no host `site.env`
- [x] 4.4 Strip Kubernetes-only kinds/fields from Pod YAML; keep kube-play Pod format
- [x] 4.5 Generate Caddyfile, Authelia, Homepage from desired + pack
- [x] 4.6 Encode lessons: keep-id/chown, lan-bind PREROUTING + OUTPUT `:443` (not `:53`), OpenCloud OIDC + loopback `auth.`, Homepage `:8443` + `169.254.1.2` scrapes, Pi-hole key = web password, PeaNUT host-net `:8092` / NUT localhost / no `AUTH_URL`, WG MTU 1280, no space recreate if xattrs exist
- [x] 4.7 NUT when UPS present; PeaNUT only if listed; implicit Cockpit all hosts and Glances all workload hosts
- [x] 4.8 SET Quadlet install/remove into system vs workload-user trees; Debian vs Ubuntu packages

## 5. SET graph and Day 2

- [x] 5.1 Implement SET order from design (disks → users → LDAP → drivers/PWM → Cockpit/Podman → secrets → NFS → generated edge → Quadlets → OpenCloud binds)
- [x] 5.2 Day 2: GET A+B, diff desired vs observed, apply delta only
- [x] 5.3 Static LAN IP only when it will not drop the Ansible session

## 6. Archive and site-agnostic sweep

- [x] 6.1 Move obsolete `bootstrap/` scripts, OMV helpers, and first-run novels into `archive/`
- [x] 6.2 Remove `MANIFEST.toml` host/role deploy contract and Materia enablement
- [x] 6.3 Sweep committed files for household hostnames, IPs, domains, and UUIDs
- [x] 6.4 Leave `windows/` in place and unhooked from GET/SET
