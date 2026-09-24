## ADDED Requirements

### Requirement: Public kube catalog layout
The repository SHALL contain environment-agnostic kube-play YAML, Quadlet `.kube` (and host-only `.container` where required), app config templates, and a Materia repository `MANIFEST.toml` under:

```
MANIFEST.toml
attributes/
components/
overlays/k8s/
bootstrap/
windows/
```

`components/<name>/` SHALL hold that app’s YAML and units. `overlays/k8s/` SHALL exist as a reserved path for a future Kubernetes site and MUST NOT be applied by Materia on this site. The catalog MUST NOT use Compose files or Komodo ResourceSync TOML as the deploy source of truth. `MANIFEST.toml` host keys SHALL be `core` and `mantle` only (not Komodo `periphery`, not Windows `surface`).

#### Scenario: Clone is deployable as a catalog
- **WHEN** a host clones the default branch
- **THEN** `MANIFEST.toml`, `components/`, and `attributes/` exist at the paths above and no ResourceSync TOML is required to deploy

#### Scenario: Host keys match the site
- **WHEN** `MANIFEST.toml` is read
- **THEN** host sections are `[Hosts.core]` and `[Hosts.mantle]` and there is no `[Hosts.periphery]` or `[Hosts.surface]`

### Requirement: No site identity in plaintext git
Committed YAML, Quadlets, templates, and `MANIFEST.toml` MUST NOT contain secrets, LAN IPs, the live domain value, or absolute disk paths such as `/srv/dev-disk-by-uuid-*`. They SHALL use placeholders whose values come from sops/age attributes or on-box env at apply time. Encrypted attribute files MAY live in git. Live age private keys MUST NOT be committed.

#### Scenario: Catalog scan
- **WHEN** committed catalog files are reviewed for site identity
- **THEN** no passwords, tokens, LAN IPs, live domain literals, or OMV uuid paths are present in plaintext

### Requirement: Config ships with the component
App config that belongs in git (Caddyfile, Homepage YAML, and similar templates) SHALL live in the component directory and SHALL be installed by Materia on apply. Operators MUST NOT be required to SCP those files onto the host by hand.

#### Scenario: Caddyfile is not hand-copied
- **WHEN** the Caddy component is applied
- **THEN** the templated Caddyfile from the catalog is the file Caddy uses, with env values supplied from attributes

### Requirement: Poll, not webhooks
Materia SHALL poll or be triggered on-site. GitHub webhooks SHALL be disabled or unused. A public clone MUST be sufficient for the default public catalog. The catalog origin SHALL be the git remote configured on each Materia host (this site uses GitHub). The catalog MUST NOT require an on-box git forge.

#### Scenario: Push does not auto-deploy via GitHub
- **WHEN** a commit is pushed to GitHub
- **THEN** GitHub does not call a webhook on this site; Materia picks up changes by on-site poll or timer

#### Scenario: Origin is the configured git remote
- **WHEN** Materia clones or updates the catalog
- **THEN** it uses the on-box git remote (not a LAN git hostname in `MANIFEST.toml`)

### Requirement: Kubernetes overlay is unused here
YAML in `components/` SHALL be limited to kinds `podman kube play` accepts (Pod, Deployment, ConfigMap, Secret, PVC, and documented Quadlet-only units). Ingress, Service, HPA, and operators MUST live only under `overlays/k8s/` (stub until a future site).

#### Scenario: Materia path has no Ingress
- **WHEN** Materia applies this site’s components
- **THEN** it does not install Kubernetes Ingress, Service, or HPA resources
