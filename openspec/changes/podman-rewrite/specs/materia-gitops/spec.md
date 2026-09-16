## ADDED Requirements

### Requirement: Materia is the on-site reconciler
Each catalog host SHALL run Materia as a systemd timer (or equivalent periodic `materia update`), not as a long-lived container that keeps `podman.sock` and D-Bus mounted. FetchIT MUST NOT be required. After a successful update, desired Quadlets SHALL be installed and the corresponding systemd units SHALL be running.

#### Scenario: Timer converges
- **WHEN** the Materia timer fires with a reachable catalog git remote
- **THEN** components assigned to that host are installed under the Quadlet directory and their systemd services are active

### Requirement: Host assignment in MANIFEST.toml
`MANIFEST.toml` SHALL assign components to literal host names `core` and `mantle`. Bootstrap MUST make Materia’s view of the hostname match those names (`core` on the NAS; `mantle` via WSL `/etc/wsl.conf`). The Windows computer name `surface` MUST NOT be a Materia host. Two hosts MUST NOT share a component instance name where a clash would result (Core Pi-hole vs mantle Pi-hole SHALL be distinct components, e.g. `pihole` and `pihole-mantle`).

#### Scenario: Core does not install Jellyfin
- **WHEN** Materia runs on `core`
- **THEN** it does not install components listed only under `[Hosts.mantle]`

### Requirement: Sops attributes and Podman secrets
Site secrets and non-public values SHALL come from sops/age attribute files (global vault plus per-host files). Materia SHALL be able to template those values into Quadlets and MAY install listed keys as Podman secrets. The age private key SHALL be created on the box and MUST NOT be committed.

#### Scenario: Host-specific secret
- **WHEN** `attributes/mantle.age` contains a value used only by a mantle component
- **THEN** applying on `core` does not require that value, and applying on `mantle` decrypts it with the on-box key

### Requirement: Root and user Quadlet trees
Core SHALL run a system (rootful) Materia timer for host plumbing (nft redirects, `wg-quick`, Scrutiny) and a user (rootless) timer for Caddy, Pi-hole, RustDesk, wg-easy UI, and other Core apps. Mantle SHALL run a user-level Materia timer as Linux user `pilot` for workload units unless a stack requires root. The Windows user `HTPC` SHALL own the WSL distro and MUST NOT be required as a Linux or Materia identity.

#### Scenario: Split Core apply
- **WHEN** both timers have succeeded on Core
- **THEN** nft redirect / `wg-quick` / Scrutiny are system units and Caddy, Pi-hole, RustDesk, wg-easy UI, and Vaultwarden are user Quadlets
