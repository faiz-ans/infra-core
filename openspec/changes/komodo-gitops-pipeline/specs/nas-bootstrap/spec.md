## ADDED Requirements

### Requirement: Interactive Core bootstrap script
The catalog SHALL include a bootstrap script intended to be copied onto the Core host (for example via SCP). The script SHALL prompt for site values (including domain, with default `home.lan` as the prompt default only, this host’s LAN IP, remote Periphery upstream IP, Komodo admin password, Vaultwarden admin token, and confirmation of detected `DATA_ROOT`) and SHALL write those values only to on-box Komodo Core and/or Periphery secret/config files—not into the git catalog. Each action SHALL also appear as commented copy-paste commands for manual use.

#### Scenario: Prompt and write
- **WHEN** an operator runs the NAS bootstrap and answers prompts
- **THEN** secrets and site values exist on the Pi in Komodo config and are not written into repository files

#### Scenario: Manual fallback
- **WHEN** the operator prefers not to run the script unattended
- **THEN** the same install and write steps are available as comments inside the script

### Requirement: Pre-GitOps software on the Pi
Bootstrap SHALL install OpenMediaVault (when using an external data disk), Docker, Komodo Core, and a local Komodo Periphery, then onboard a Komodo server named `CORE_SERVER` (default `core`). When using an external disk it SHALL mount it at the OMV uuid path and use that as `DATA_ROOT`. When using the OS disk it SHALL use a directory such as `/srv/core`. It SHALL create the `DATA_ROOT` directory contract. After Core is up, it SHALL enable ResourceSync against this public repo with webhooks off.

#### Scenario: Fresh Pi OS Lite
- **WHEN** bootstrap completes on Raspberry Pi OS Lite 64-bit with an OMV data disk attached
- **THEN** Docker, Komodo Core, and Periphery are installed, the Core server resource exists under `CORE_SERVER` (default `core`), `DATA_ROOT` is set, and ResourceSync is configured to poll the catalog

### Requirement: OMV install must not steal the SSH session
When bootstrap installs OpenMediaVault over SSH, it SHALL invoke the vendor install script with skip-network (`-n`) and skip-reboot (`-r`) so the installer does not purge NetworkManager, rewrite systemd-networkd, or reboot. After the installer returns, bootstrap SHALL verify an IPv4 default route still exists before continuing.

#### Scenario: Installer keeps DHCP
- **WHEN** bootstrap runs the OMV installer on a host that already has a working LAN address
- **THEN** that address remains reachable over SSH when the installer finishes, and the host is not rebooted by the vendor script

### Requirement: OMV workbench does not occupy HTTP/HTTPS
When OpenMediaVault is installed, bootstrap SHALL move the OMV workbench off host ports 80 and 443 so Caddy can bind them. The workbench HTTP listen port SHALL be taken from the OMV configuration database (`conf.webadmin.port`), not from `OMV_NGINX_SITE_WEBGUI_LISTEN_PORT`. After the change, workbench SHALL listen on port 81 and OMV SHALL NOT terminate TLS on 443.

#### Scenario: Caddy can bind 80 and 443
- **WHEN** bootstrap has installed OMV and applied the workbench port change
- **THEN** host nginx listens on 81 (not 80/443) and Caddy can publish `80:80` and `443:443`

### Requirement: Komodo Core is not a catalog chicken-egg
Komodo Core (and the first local Periphery) SHALL be brought up by bootstrap, not by ResourceSync. After Core exists, ResourceSync MAY manage other stacks. Bootstrap MAY later adopt Core as a visible stack but MUST remain able to start Core without Komodo already running.

#### Scenario: Empty box
- **WHEN** Komodo is not yet running on the Pi
- **THEN** bootstrap can still install and start Core without pulling a stack through ResourceSync
