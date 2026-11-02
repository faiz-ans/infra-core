## MODIFIED Requirements

### Requirement: Public kube catalog layout
The repository SHALL contain a site-agnostic catalog:

```
schema/
examples/site.example.yaml
ansible/
components/
windows/
archive/
```

`components/<name>/` SHALL hold that app’s Quadlet/Pod YAML and official-pack metadata. `windows/` SHALL remain for HTPC/Windows helpers not driven by GET/SET. The catalog MUST NOT use Compose files, Komodo ResourceSync, or `MANIFEST.toml` host keys as the deploy source of truth.

#### Scenario: Clone is deployable as a catalog
- **WHEN** a host or operator clones the default branch
- **THEN** `schema/`, `examples/site.example.yaml`, `ansible/`, and `components/` exist and no ResourceSync TOML is required to deploy

### Requirement: No site identity in plaintext git
Committed YAML, Quadlets, schema, and example topology MUST NOT contain secrets, LAN IPs, a live domain value, or absolute disk UUIDs from a household. Values SHALL come from local desired `site.yaml` and SOPS at SET time. Age private keys MUST NOT be committed.

#### Scenario: Catalog scan
- **WHEN** committed catalog files are reviewed for site identity
- **THEN** no passwords, tokens, LAN IPs, live domain literals, or household disk UUIDs are present in plaintext

### Requirement: Config ships with the component
App config that belongs in git (Caddyfile/Authelia templates or generators, Homepage defaults) SHALL live in the component or Ansible template tree and SHALL be installed by SET. Operators MUST NOT be required to SCP those files onto the host by hand.

#### Scenario: Caddyfile is not hand-copied
- **WHEN** Caddy is SET
- **THEN** the generated Caddyfile from the catalog is the file Caddy uses

## REMOVED Requirements

### Requirement: Public catalog layout
**Reason**: Compose + Komodo ResourceSync is no longer the catalog.
**Migration**: Use `ansible/` + `components/` + `schema/`.

### Requirement: Poll, not webhooks
**Reason**: Materia poll is not a deploy path.
**Migration**: Operator machine runs Ansible GET/SET.

### Requirement: Generated ResourceSync as catalog contract
**Reason**: Topology now drives Ansible inventory, not ResourceSync TOML.
**Migration**: Desired `site.yaml` is the placement authority.
