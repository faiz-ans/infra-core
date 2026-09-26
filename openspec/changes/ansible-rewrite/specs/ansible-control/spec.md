## ADDED Requirements

### Requirement: Push-based runner on the operator machine
The product SHALL apply and inspect sites by Ansible playbooks run from the operator’s machine (push). Hosts MUST NOT be required to pull git or run Materia/ansible-pull. Inventory SHALL be generated from desired topology (or Day 0 IP + admin-user input).

#### Scenario: No on-host git poll
- **WHEN** SET completes
- **THEN** no Materia timer or ansible-pull unit is installed as part of this change

### Requirement: GET Task A is a host census
Given SSH reachability (IP + admin username), GET Task A SHALL record hostname, MAC, OS name and version, timezone, locale, block devices, GPUs, UPS USB devices, PWM hwmon path if present, and local users with uid greater than 1000 (name, uid, gid). It MUST NOT require roles or services to be declared.

#### Scenario: Bare host facts
- **WHEN** the operator runs GET A against a freshly imaged Debian host
- **THEN** observed (or the printed scaffold) includes hostname, MAC, OS, `lsblk` disks, and uid>1000 users

### Requirement: GET Task B is site-influenced state
GET Task B SHALL record mounted disks, SMB/NFS exports, presence of Cockpit and Podman, deployed containers, and LDAP join state plus directory identifiers when LDAP is deployed.

#### Scenario: After SET, observed lists containers
- **WHEN** SET has deployed Caddy and Authelia and the operator runs GET B
- **THEN** observed lists those containers and whether Cockpit and Podman are installed

### Requirement: SET is idempotent and OS-aware
SET SHALL configure each host to match desired topology using Debian or Ubuntu packages according to gathered `os.name`. A second SET with the same desired file MUST NOT fail or rewrite unchanged secrets.

#### Scenario: Second SET is a no-op for running units
- **WHEN** the operator runs SET twice with an unchanged desired file
- **THEN** the second run exits 0 and already-correct Quadlets remain running

### Requirement: Day 2 applies a desired-versus-observed diff
Day 2 SHALL run GET A+B, compare desired to observed, and SET only the delta (add/remove services, mounts, accounts, exports). Removing a service SHALL uninstall that unit. Removing a site user SHALL delete the account only.

#### Scenario: Service removed from desired
- **WHEN** observed has PeaNUT and the operator deletes PeaNUT from desired and runs Day 2
- **THEN** SET stops and removes the PeaNUT Quadlet and does not delete NUT device data

### Requirement: Supported host OS
SET and GET SHALL support Ubuntu and Debian. Other OS families MUST fail with an explicit unsupported-OS error.

#### Scenario: Unsupported OS
- **WHEN** GET A reports `os.name` other than ubuntu or debian
- **THEN** SET exits non-zero and names the unsupported OS
