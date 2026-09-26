## MODIFIED Requirements

### Requirement: Apply script installs Quadlets from roles
Ansible SET SHALL read desired topology, resolve catalog templates, install Quadlets into system (rootful) or the workload user’s Quadlet directory (rootless), and reload/start the units. A Materia binary and `bootstrap/apply.sh` MUST NOT be required.

#### Scenario: SET without Materia
- **WHEN** the operator runs SET for a host that lists Caddy and Authelia and has no `materia` binary
- **THEN** those Quadlets are installed and SET exits 0

### Requirement: Catalog units do not use Materia template APIs
Committed default Quadlets and Pod YAML MUST NOT depend on `m_outputDir`, `m_dataDir`, or Materia-only `.gotmpl`. After SET, a `.kube` `Yaml=` path SHALL refer to a rendered `pod.yaml` in that app’s Quadlet directory.

#### Scenario: Yaml path is local to the unit
- **WHEN** Authelia is SET
- **THEN** the installed `authelia.kube` `Yaml=` points at a `pod.yaml` beside that unit and that file exists

### Requirement: No site identity in plaintext git
Committed YAML and Quadlets MUST NOT contain secrets, LAN IPs, a live domain value, or household disk UUIDs. Values SHALL come from desired topology and SOPS at SET time.

#### Scenario: Catalog scan
- **WHEN** committed catalog files are reviewed for site identity
- **THEN** no passwords, tokens, LAN IPs, live domain literals, or household uuid paths are present in plaintext
