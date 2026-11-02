## ADDED Requirements

### Requirement: OpenLDAP is optional source of truth
When `identity.ldap` is `openldap` and a workload host lists OpenLDAP, that directory SHALL be the source of truth for unix/SMB on storage hosts that own `groups` or `users`, and for Authelia. GET SHALL record LDAP unique identifiers for site users. When `identity.ldap` is `none`, SET SHALL still create disjoint unix accounts on those storage hosts and Authelia file-backend users.

#### Scenario: LDAP placed
- **WHEN** desired sets `identity.ldap: openldap` and lists `openldap` on a workload host
- **THEN** SET deploys OpenLDAP, joins owning storage hosts, and Authelia uses LDAP

#### Scenario: LDAP named but not placed
- **WHEN** desired sets `identity.ldap: openldap` and no host lists `openldap`
- **THEN** SET fails with a placement error

### Requirement: User roles
`sysadmin` SHALL receive sudo and SSH on the host where it is listed under `hosts[].users`. `sysuser` SHALL receive neither. `appadmin` and `appuser` SHALL map to SSO admin vs standard roles. SET SHALL create a user-home for each unique `site.users` entry and a group-home for each unique `site.users[].groups` value, and grant SMB access accordingly.

#### Scenario: Group home
- **WHEN** two site users list `groups: [family]`
- **THEN** SET creates `groups/family` and both users can access it over SMB

### Requirement: SSH key-only is gated
When `identity.ssh` is `key-only` (site-wide or host `identity.ssh`), SET MUST NOT disable password SSH until that host has at least one `sysadmin` with an `ssh-keys` entry applied.

#### Scenario: Key-only without a key
- **WHEN** desired sets `identity.ssh: key-only` and the only sysadmin has no `ssh-keys`
- **THEN** SET fails and password SSH remains enabled

### Requirement: Account delete does not delete homes
Removing a site user from desired SHALL delete unix and/or LDAP and SSO accounts only. Home and group directories MUST remain.

#### Scenario: Re-add after delete
- **WHEN** a site user is removed, SET runs, then the same name is added back and SET runs
- **THEN** a new account exists and the previous home directory is still on disk
