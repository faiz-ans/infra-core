## ADDED Requirements

### Requirement: From-scratch OS is the default story
The catalog SHALL document Core bring-up as: image the OS disk, install Layer 0, remount or format-empty `DATA_ROOT`, apply bootstrap roles, then full roles. It MUST NOT document Docker volume export, Komodo purge, or in-place engine conversion as the happy path.

#### Scenario: README happy path has no Docker cutover
- **WHEN** an operator follows the root README and `bootstrap/` entry doc
- **THEN** the numbered steps are flash-or-new-OS, remount-or-empty-disk, Layer 0, phase A apply, gates, phase B, and they are not instructed to export Docker named volumes or run a Komodo purge

### Requirement: This site may remount a populated data disk
When a site already has household data on an extra disk, bootstrap SHALL remount that filesystem as `DATA_ROOT` and MUST NOT require wiping it. Operators MAY restore saved app config (Vaultwarden export or live dir, Caddy PKI, Authelia file-backend users, Homepage YAML) onto that tree. Authelia sqlite from a previous storage key MUST NOT be required.

#### Scenario: IronWolf contents survive OS re-image
- **WHEN** the OS disk is re-imaged and the existing ext4 data disk is mounted at `/srv/dev-disk-by-uuid-<uuid>`
- **THEN** `system/`, `shared/`, and `users/` from before the re-image are present and bootstrap does not format that disk

### Requirement: Phased apply before full catalog
A new or re-imaged Core SHALL apply `core-bootstrap` (edge + OpenCloud) and reach OpenCloud/layout/NFS gates before `core-full`. Mantle SHALL apply `mantle-bootstrap` before `mantle-full`. Mantle full roles MUST NOT be required while mantle is idle.

#### Scenario: First apply is bootstrap only
- **WHEN** the committed `MANIFEST.toml` is used unchanged after Layer 0
- **THEN** `[Hosts.core]` lists `core-bootstrap` only and `[Hosts.mantle]` lists `mantle-bootstrap` only
