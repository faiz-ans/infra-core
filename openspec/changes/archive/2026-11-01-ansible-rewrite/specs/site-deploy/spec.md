## MODIFIED Requirements

### Requirement: From-scratch OS is the default story
The catalog SHALL document site bring-up as: image or use existing Debian/Ubuntu hosts, Day 0 GET Task A (IPs + admin users), write desired `site.yaml`, Day 1 SET, then Day 2 GET+diff+SET. It MUST NOT document Docker volume export, Komodo purge, `core.sh`, or `apply.sh` as the happy path.

#### Scenario: README happy path is GET then SET
- **WHEN** an operator follows the root README
- **THEN** the numbered steps are GET facts, edit desired topology, SET, and they are not instructed to export Docker named volumes or run a Komodo purge

### Requirement: This site may remount a populated data disk
When a disk already has household data, desired topology SHALL mount it by UUID once and MAY declare a typed `import` list (`users-root` / `user-home`, `groups-root` / `group-home`, `appdata-root` / `appdata-home`) whose `from:` paths are relative to that disk mount. SET MUST NOT require wiping that disk. Authelia sqlite from a previous storage key MUST NOT be required.

#### Scenario: Existing ext4 disk is imported not formatted
- **WHEN** desired names a disk UUID that already has ext4 data and an `import` block
- **THEN** SET mounts that UUID and does not format the filesystem

### Requirement: Phased apply before full catalog
A new site SHALL be allowed to SET a subset of official services (storage + identity + ingress first). Full official catalog MUST NOT be required on the first SET. Windows/HTPC setup remains outside GET/SET.

#### Scenario: First SET can omit mantle-full services
- **WHEN** desired lists storage, Caddy, Authelia, and OpenCloud only
- **THEN** SET succeeds without placing Immich, Jellyfin, or other unofficially required apps
