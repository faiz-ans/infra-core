## ADDED Requirements

### Requirement: Vaultwarden runs on the NAS
The catalog SHALL provide a Vaultwarden Compose stack deployed by Komodo ResourceSync to server `nas` (the Raspberry Pi). The stack SHALL join the same Docker edge network as Caddy, Authelia, and Homepage so those services can reach it by container name. Persistent data SHALL live at `${DATA_ROOT}/system/vaultwarden`. Site-specific values (public URL, admin token, signup flag) SHALL come from Komodo variables or secrets and MUST NOT appear in the git catalog.

#### Scenario: Deploy on nas
- **WHEN** ResourceSync applies the NAS stacks
- **THEN** Vaultwarden is running on `nas` with data under `${DATA_ROOT}/system/vaultwarden` and no host IPs, domains, or tokens committed in compose or config files

### Requirement: Authelia protects only /admin
Caddy SHALL reverse-proxy `vault.{$DOMAIN}` to Vaultwarden. Authelia forward auth SHALL apply only to `/admin` (and `/admin/*`). The web vault, Bitwarden client API, icons, events, and websocket notification paths MUST NOT go through Authelia; Vaultwarden SHALL authenticate those itself.

#### Scenario: Client sync bypasses Authelia
- **WHEN** an official Bitwarden client calls `/api/*`, `/icons/*`, `/events/*`, or `/notifications/*` on `vault.{$DOMAIN}`
- **THEN** Caddy proxies to Vaultwarden without Authelia forward auth

#### Scenario: Admin UI requires Authelia
- **WHEN** a browser requests `/admin` or `/admin/*` on `vault.{$DOMAIN}`
- **THEN** Caddy enforces Authelia forward auth before proxying to Vaultwarden

### Requirement: Homepage uses public href and internal scrape
Homepage SHALL link Vaultwarden with a public href on `vault.{{HOMEPAGE_VAR_DOMAIN}}` (through Caddy) and SHALL monitor or scrape it via the internal URL `http://vaultwarden:80` (edge network), not through Authelia.

#### Scenario: Widget does not hit Authelia
- **WHEN** Homepage checks Vaultwarden
- **THEN** the request goes to `http://vaultwarden:80` and does not require an Authelia session

### Requirement: Vault data is included in NAS backup
Restic on the NAS SHALL include `${DATA_ROOT}/system/vaultwarden` in the backup set sent to the HTPC Restic REST target.

#### Scenario: Restore includes the vault
- **WHEN** a NAS restic snapshot is taken
- **THEN** Vaultwarden persistent data under `system/vaultwarden` is part of that snapshot
