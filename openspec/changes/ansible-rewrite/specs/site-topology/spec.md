## ADDED Requirements

### Requirement: Desired topology is a list-of-hosts document
The product SHALL accept a desired topology (`site.yaml`) whose `hosts` are a YAML list of objects. Hostnames and IP addresses SHALL be field values, not map keys. Committed git MUST ship a JSON schema and an example topology that contains no live household hostname, LAN IP, disk UUID, or person name.

#### Scenario: Example has no site identity
- **WHEN** `examples/site.example.yaml` is reviewed
- **THEN** it uses placeholders (not this lab’s IPs, MACs, UUIDs, or user names) and validates against the schema

### Requirement: Observed is a separate GET artifact
GET SHALL write observed state to a file distinct from desired `site.yaml`. GET MUST NOT modify an existing desired file. A Day 0 facts-only run MAY print a scaffold the operator copies into a new desired file.

#### Scenario: Day 2 GET leaves desired intact
- **WHEN** the operator has a desired `site.yaml` and runs GET A+B
- **THEN** only the observed file is rewritten and every desired `roles`, `users`, `import`, and PWM `scale` field is unchanged

### Requirement: Site-level keys are policy not placement
Keys under `site.data`, `site.networking`, `site.identity`, and `site.operations` that name an engine SHALL be treated as site-wide policy. SET SHALL error if a non-`none` engine is not also listed under a workload host’s services, except Cockpit (every host) and Glances (every workload host). OpenLDAP SHALL require an explicit workload placement.

#### Scenario: DNS engine without instance
- **WHEN** desired has `networking.dns: pi-hole` and no host lists `pi-hole`
- **THEN** SET fails with a placement error and does not install Pi-hole

#### Scenario: Cockpit is implicit on all hosts
- **WHEN** desired has `operations.host.manager: cockpit`
- **THEN** SET installs Cockpit on every host even if it is omitted from `services`

### Requirement: Three logical data roots
Desired topology SHALL declare `data.roots` `appdata`, `groups`, and `users` as relative paths (defaults `/appdata`, `/groups`, `/users`). Each root MUST be owned by exactly one storage drive on one host.

#### Scenario: Split ownership is allowed
- **WHEN** host A’s storage drive owns `appdata` and host B’s drive owns `users` and `groups`
- **THEN** the schema accepts the file and SET mounts each root on its owner

### Requirement: Site users and host-local users
`site.users` SHALL describe site people (homes, groups, SSO roles). `hosts[].users` SHALL describe local-only accounts. Valid roles are `sysadmin`, `sysuser`, `appadmin`, and `appuser`. At least one `sysadmin` MUST exist on each host.

#### Scenario: Site person is not SSH
- **WHEN** a site user has roles `[sysuser, appadmin]` only
- **THEN** SET does not grant sudo or SSH on hosts
