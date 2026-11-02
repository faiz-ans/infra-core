## REMOVED Requirements

### Requirement: Materia is not part of default bootstrap
**Reason**: Materia is removed, not merely optional.
**Migration**: Do not install Materia.

### Requirement: Optional Materia wraps the same apply path
**Reason**: There is no apply.sh for a timer to wrap.
**Migration**: Operator runs Ansible SET.

### Requirement: Age vaults are optional with Materia
**Reason**: Age/SOPS is the secret path for SET, independent of Materia.
**Migration**: catalog-templates secrets requirement.
