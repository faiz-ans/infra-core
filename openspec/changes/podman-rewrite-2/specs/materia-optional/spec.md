## ADDED Requirements

### Requirement: Materia is not part of default bootstrap
Core and mantle Layer 0 MUST complete without installing Materia. Enabling Materia SHALL be a separate operator action after Layer 0 (and MAY be skipped forever). FetchIT MUST NOT be required. Future-site GitOps (Materia, ansible-pull, Argo, or none) SHALL remain unspecified by this catalog.

#### Scenario: New OS has no Materia timer
- **WHEN** Layer 0 finishes and the operator has not run the optional enable script
- **THEN** no Materia systemd timer is enabled and stacks are still installable via the default apply entrypoint

### Requirement: Optional Materia wraps the same apply path
If Materia is enabled on a host, it SHALL update the catalog git remote and invoke the same apply entrypoint used without Materia. It MUST NOT render a parallel `.gotmpl` / `m_dataDir` tree that overwrites default Quadlets with a second dialect.

#### Scenario: Timer does not fork the catalog
- **WHEN** optional Materia is enabled and its timer fires
- **THEN** the Quadlets on disk are those produced by the default apply entrypoint for the host’s roles

### Requirement: Age vaults are optional with Materia
Default apply SHALL use `/etc/infra-core/site.env`. Encrypted `attributes/*.age` files and an on-box age private key MAY exist when Materia is enabled and MUST NOT be required for Layer 0 or default apply. Age private keys MUST NOT be committed.

#### Scenario: Apply without age key
- **WHEN** `/etc/infra-core/site.env` is present and `/etc/materia/age.key` is absent
- **THEN** default apply for `core-bootstrap` still substitutes site values and installs Quadlets
