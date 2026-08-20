## ADDED Requirements

### Requirement: Interactive NAS bootstrap script
The catalog SHALL include a bootstrap script intended to be copied onto the Pi (for example via SCP). The script SHALL prompt for site values (including domain, with default `home.lan` as the prompt default only, NAS LAN IP, HTPC upstream IP, Komodo admin password, Vaultwarden admin token, and confirmation of detected `DATA_ROOT`) and SHALL write those values only to on-box Komodo Core and/or Periphery secret/config files—not into the git catalog. Each action SHALL also appear as commented copy-paste commands for manual use.

#### Scenario: Prompt and write
- **WHEN** an operator runs the NAS bootstrap and answers prompts
- **THEN** secrets and site values exist on the Pi in Komodo config and are not written into repository files

#### Scenario: Manual fallback
- **WHEN** the operator prefers not to run the script unattended
- **THEN** the same install and write steps are available as comments inside the script

### Requirement: Pre-GitOps software on the Pi
Bootstrap SHALL install OpenMediaVault, Docker, Komodo Core, and a local Komodo Periphery, then onboard Komodo server name `nas`. It SHALL detect or confirm the OMV data mount and use that path as `DATA_ROOT` for `nas`. It SHALL create the `DATA_ROOT` directory contract (or invoke the step that does). After Core is up, it SHALL enable ResourceSync against this public repo with webhooks off.

#### Scenario: Fresh Pi OS Lite
- **WHEN** bootstrap completes on Raspberry Pi OS Lite 64-bit with an OMV data disk attached
- **THEN** OMV, Docker, Komodo Core, and Periphery are installed, server `nas` exists, `DATA_ROOT` is set to the uuid data path, and ResourceSync is configured to poll the catalog

### Requirement: Komodo Core is not a catalog chicken-egg
Komodo Core (and the first local Periphery) SHALL be brought up by bootstrap, not by ResourceSync. After Core exists, ResourceSync MAY manage other stacks. Bootstrap MAY later adopt Core as a visible stack but MUST remain able to start Core without Komodo already running.

#### Scenario: Empty box
- **WHEN** Komodo is not yet running on the Pi
- **THEN** bootstrap can still install and start Core without pulling a stack through ResourceSync
