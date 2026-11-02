## REMOVED Requirements

### Requirement: Materia is the on-site reconciler
**Reason**: Deploy is push-based Ansible from the operator machine.
**Migration**: `ansible-control` GET/SET.

### Requirement: Host assignment in MANIFEST.toml
**Reason**: `MANIFEST.toml` host keys are site identity.
**Migration**: Desired `site.yaml` host list.

### Requirement: Sops attributes and Podman secrets
**Reason**: Replaced by catalog-templates SOPS on the runner.
**Migration**: Age/SOPS beside local desired topology; Podman secrets at SET.

### Requirement: Root and user Quadlet trees
**Reason**: Quadlet install is SET’s job.
**Migration**: ansible-control + catalog-templates.
