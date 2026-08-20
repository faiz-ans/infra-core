## ADDED Requirements

### Requirement: Public catalog layout
The repository SHALL contain environment-agnostic Compose files, app config templates, and Komodo ResourceSync TOML under:

```
stacks/platform/
stacks/workload/
stacks/komodo/
bootstrap/
windows/
```

ResourceSync TOML SHALL assign stacks to Komodo server names via `[[CORE_SERVER]]` and `[[PERIPHERY_SERVER]]` (not hostnames or IPs). Bootstrap defaults those names to `core` and `periphery`; a site MAY override them (for example `nas` and `htpc`). Stacks SHALL point at this git repo and a `run_directory` inside `stacks/`.

#### Scenario: Clone is deployable as a catalog
- **WHEN** a host clones the default branch
- **THEN** platform and workload compose directories and ResourceSync TOML exist at the paths above

### Requirement: No site identity in git
Committed compose, config templates, and ResourceSync files MUST NOT contain secrets, LAN IPs, the live domain value, or absolute disk paths such as `/srv/dev-disk-by-uuid-*`. They SHALL use interpolation placeholders (`${VAR}`, `{$VAR}`, `[[VAR]]`, `{{HOMEPAGE_VAR_…}}`) whose values come from Komodo at deploy time. ResourceSync MUST NOT declare secret variable values. The NAS bootstrap script MAY use `home.lan` only as an interactive prompt default, not as a value written into compose or ResourceSync.

#### Scenario: Catalog scan
- **WHEN** committed compose, config templates, and ResourceSync TOML are reviewed for site identity
- **THEN** no passwords, tokens, LAN IPs, live domain literals, or OMV uuid paths are present in those files

### Requirement: Config ships with the stack
App config that belongs in git (Caddyfile, Homepage YAML, and similar templates) SHALL live beside the stack compose file and SHALL be cloned and used by Komodo on deploy. Operators MUST NOT be required to SCP or copy those files onto the host by hand.

#### Scenario: Caddyfile is not hand-copied
- **WHEN** the Caddy stack is deployed from git
- **THEN** the templated Caddyfile from the catalog is the file Caddy uses, with env values supplied by Komodo

### Requirement: Poll, not webhooks
Komodo ResourceSync and stack git sources SHALL poll or be triggered on-site. GitHub webhooks SHALL be disabled (`webhook_enabled` false or equivalent). A public clone MUST be sufficient; deploy credentials for GitHub MUST NOT be required for the default public catalog.

#### Scenario: Push does not auto-deploy via GitHub
- **WHEN** a commit is pushed to GitHub
- **THEN** GitHub does not call a webhook on this site; Komodo picks up changes by poll or manual sync on-site
