## ADDED Requirements

### Requirement: Cockpit on Core
Core SHALL run Cockpit with the Podman plugin so an operator can list containers, read journals, and restart systemd units from a browser. It SHALL be lightweight (no Portainer or Komodo). It MAY be proxied by Caddy on a catalogued hostname with Cockpit’s own authentication, not Authelia, unless later opted in.

#### Scenario: Restart Caddy from the GUI
- **WHEN** an operator opens Cockpit on Core and restarts the Caddy unit
- **THEN** systemd restarts that Quadlet without Komodo

### Requirement: Mantle Cockpit is optional
The catalog MUST NOT require Cockpit on `mantle`. Homepage, Glances, and Uptime Kuma SHALL be sufficient for mantle up/down. Bootstrap MAY document optional WSL Cockpit.

#### Scenario: Mantle without Cockpit
- **WHEN** mantle stacks are running and Cockpit is not installed in WSL
- **THEN** the site is still considered complete for this capability
