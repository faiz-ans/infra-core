## ADDED Requirements

### Requirement: Push-based runner on the operator machine
The product SHALL apply and inspect sites by Ansible playbooks run from the operator’s machine (push). Hosts MUST NOT be required to pull git or run Materia/ansible-pull. Inventory SHALL be generated from desired topology (or Day 0 IP + admin-user input).

#### Scenario: No on-host git poll
- **WHEN** SET completes
- **THEN** no Materia timer or ansible-pull unit is installed as part of this change

### Requirement: GET Task A is a host census
Given SSH reachability (IP + admin username), GET Task A SHALL record only facts present on the host: live hostname, MAC, OS, timezone, locale (from `/etc/default/locale`), block devices (including WSL virtual disks as internal; scaffold `resources.disks` keeps the kernel name as `id`. A disk with data partitions lists those under `partitions` (`id`, `name` from the disk MODEL or the partition name, `size`, `uuid`); boot and swap partitions are omitted. A disk with no partitions keeps `name`, `size`, and `uuid` on itself. A disk with neither a data-partition UUID nor a filesystem UUID on the disk is omitted (WSL system VHDs such as the unmounted ~357M and ~159M ext4 disks). Storage drives and host roots use the partition id when partitions are present, otherwise the disk id. SET still mounts by that volume's uuid), GPUs (`lspci` NVIDIA/GeForce or `nvidia-smi` on the site host — PATH and `/usr/lib`; Microsoft Basic Render is not NVIDIA), USB devices that are plug-in peripherals (`/sys/bus/usb` and `lsusb` vendor:product, bus, device, name). GET MUST omit USB root hubs, hub chips, and USB-ethernet NICs from both observed and the scaffold (same idea as omitting loop/zram disks from the scaffold). No device-class guess for UPS vs other peripherals. Census JSON is not re-parsed as YAML so names like `Inc.` are not dropped. PWM hwmon path if present, and local users with uid ≥ 1000 (name, uid, gid, authorized_keys, and `sysadmin` true when the account is in `sudo`/`admin`/`wheel` or `sudo -l` shows it may run commands, otherwise false). The printed scaffold MUST NOT invent users, roles, domains, engines, or USB `type`. Observed `sshd` policy (`true` / `false` / `key-only`) goes to `site.identity.ssh` only when every host matches; otherwise each host `identity.ssh`. Timezone/locale go to `site.env` only when every host matches; otherwise each host `env`.

#### Scenario: Bare host facts
- **WHEN** the operator runs GET A against a freshly imaged Debian host
- **THEN** observed (or the printed scaffold) includes the live hostname, MAC, OS, real `lsblk` disks, and uid≥1000 users including uid 1000

### Requirement: GPU facts come from the site host
GET Task A SHALL enumerate NVIDIA GPUs using tools on that site host: `lspci` and `nvidia-smi` (on PATH and under `/usr/lib`). It MUST NOT query a hypervisor or another OS the site host might be running on, and MUST NOT walk `/mnt`. Microsoft Basic Render is not NVIDIA. GET MUST NOT install packages or prompt the operator. The printed scaffold SHALL include `resources.gpu` only after `nvidia-smi -L` lists a GPU; each entry’s `id` SHALL be `gpu<index>` from that listing, with `name` and `uuid`. Scaffold MUST NOT invent `gpu0` or a CDI `device` field.

#### Scenario: nvidia-smi off PATH
- **WHEN** the site host has `nvidia-smi` under `/usr/lib` and `-L` lists `GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-…)`
- **THEN** the scaffold GPU id is `gpu0` and includes that name and UUID

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
