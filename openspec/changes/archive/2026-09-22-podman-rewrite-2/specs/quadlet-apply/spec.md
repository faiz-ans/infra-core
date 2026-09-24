## ADDED Requirements

### Requirement: Apply script installs Quadlets from roles
The catalog SHALL provide an apply entrypoint that reads host roles (from `MANIFEST.toml` or an equivalent role list), substitutes on-box site values into component Quadlets and kube YAML, installs them into the Podman Quadlet directories (system for rootful units, user `pilot` for rootless), and reloads/starts the corresponding systemd units. A Materia binary MUST NOT be required for this apply.

#### Scenario: Phase A without Materia
- **WHEN** the operator runs apply for `core-bootstrap` on a host that has `/etc/infra-core/site.env` and no `materia` binary
- **THEN** Caddy, Authelia, Pi-hole, Homepage, and OpenCloud Quadlets are installed and the apply exits 0

### Requirement: Catalog units do not use Materia template APIs
Committed default Quadlets and kube YAML MUST NOT depend on `m_outputDir`, `m_dataDir`, or Materia-only `.gotmpl` as the source of truth. After apply, a `.kube` `Yaml=` path SHALL refer to a rendered `pod.yaml` in the Quadlet directory for that app.

#### Scenario: Yaml path is local to the unit
- **WHEN** Authelia is applied
- **THEN** the installed `authelia.kube` `Yaml=` points at a `pod.yaml` beside that unit (or an equivalent non-`/var/lib/materia/output` path) and that file exists

### Requirement: No site identity in plaintext git
Committed YAML, Quadlets, and `MANIFEST.toml` MUST NOT contain secrets, LAN IPs, the live domain value, or absolute disk paths such as `/srv/dev-disk-by-uuid-*`. Values SHALL come from `/etc/infra-core/site.env` (or equivalent) at apply time.

#### Scenario: Catalog scan
- **WHEN** committed catalog files are reviewed for site identity
- **THEN** no passwords, tokens, LAN IPs, live domain literals, or OMV uuid paths are present in plaintext
