## ADDED Requirements

### Requirement: Generated ResourceSync as catalog contract

The git catalog SHALL treat the declarative topology document as the authority for stack-to-server placement and phase. Committed ResourceSync TOML under `stacks/komodo/` SHALL be the generator output (including `stacks-bootstrap.toml` and per-server full-phase files). Compose and config templates remain free of secrets, LAN IPs, live domains, and absolute disk paths; topology MUST likewise omit those values. Literal Komodo `server` names in generated TOML MUST match on-site server resources.

#### Scenario: Public clone has usable sync files

- **WHEN** a site clones the catalog after topology generation for its servers
- **THEN** ResourceSync can apply `stacks-bootstrap.toml` then the phase-full TOML files without hand-authoring stack blocks
