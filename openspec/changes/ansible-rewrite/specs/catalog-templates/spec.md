## ADDED Requirements

### Requirement: Official service pack
The catalog SHALL treat as officially integrated only the services already shipped under `components/` plus OpenLDAP, and MUST NOT implement comment-only engines (Traefik, Authentik, Nextcloud, and similar). Each official service SHALL declare default subdomains, ports, SSO mode (OIDC or forward-auth), tile and monitor defaults, and network mode. A UPS resource SHALL enable NUT only; PeaNUT SHALL deploy only when listed.

#### Scenario: UPS without PeaNUT
- **WHEN** a host has a UPS device and desired does not list PeaNUT
- **THEN** SET enables NUT and does not deploy a PeaNUT container

### Requirement: Topology variable resolution
SET SHALL resolve `${site.*}`, `${host.*}`, and `${secrets.*}` in Quadlet and Pod YAML from desired topology and SOPS. `${site.data.roots.*}` SHALL become a local path or an inferred NFS mount per native-storage. `${site.networking.ingress.host.ip}` SHALL be the IP of the unique host that lists the ingress engine, or SET SHALL error if zero or more than one such host exists.

#### Scenario: Two ingress instances
- **WHEN** two hosts list Caddy and `networking.ingress` is `caddy`
- **THEN** SET fails and does not generate a Caddyfile

### Requirement: Secrets are SOPS then Podman secrets
Secrets SHALL be Age/SOPS on the operator machine and installed as Podman secrets on the workload host. SET MUST NOT write a host-wide plaintext `.env` equivalent to `/etc/infra-core/site.env`.

#### Scenario: No site.env on host
- **WHEN** SET has deployed Authelia
- **THEN** `/etc/infra-core/site.env` is not required and Authelia still receives its secrets via Podman or unit environment from the runner

### Requirement: Pod YAML without Kubernetes-only fields
Official units SHALL remain kube-play Pod YAML (or existing single-process `.container` / `.network` files). Committed YAML MUST NOT include Ingress, Service, HPA, or other kinds kube-play does not apply.

#### Scenario: Catalog scan for unused kinds
- **WHEN** `components/` YAML is scanned
- **THEN** no `kind: Ingress` or `kind: Service` documents are present

### Requirement: Encoded live-site lessons
Generated Caddy, Authelia, OpenCloud, Homepage, PeaNUT, lan-bind, and WireGuard MUST include the already-proven constraints: Caddy and Authelia `UserNS=keep-id` plus data-dir chown; lan-bind PREROUTING `:80/:443/:53` and OUTPUT `127.0.0.1` (and NAS LAN IP) `:443` → Caddy high port without OUTPUT `:53`; OpenCloud opaque-token verify `none`, autoprovision, and `auth.` via pasta loopback; Homepage allowed hosts include `:8443` and host scrapes use `169.254.1.2`; Pi-hole widget key is the web password; PeaNUT is host-net on `:8092` with NUT at `127.0.0.1` and no `AUTH_URL`; WireGuard MTU is 1280; OpenCloud spaces are not recreated when `user.oc.space.*` xattrs exist.

#### Scenario: OpenCloud can reach Authelia well-known
- **WHEN** OpenCloud and Authelia are SET on a site-network host behind Caddy high ports
- **THEN** from the OpenCloud container `https://auth.<domain>/.well-known/openid-configuration` succeeds (not connection-refused to the LAN IP on `:443`)

### Requirement: Generated edge and dashboard config
When Caddy is the ingress engine and placed, SET SHALL generate the Caddyfile from placed services’ subdomains and official SSO mode. When Authelia is the SSO engine and placed, SET SHALL generate clients, claims, and access rules from the same list. When Homepage is placed, SET SHALL generate tiles from services with `tile` true (default true).

#### Scenario: New official service gets a vhost
- **WHEN** desired lists Jotty with primary subdomain `notes`
- **THEN** the generated Caddyfile contains `notes.<domain>` and Authelia has the official Jotty client or forward-auth rule
