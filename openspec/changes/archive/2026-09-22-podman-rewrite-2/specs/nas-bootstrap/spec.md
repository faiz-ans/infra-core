## ADDED Requirements

### Requirement: Layer 0 does not install Materia
Core bootstrap (`core.sh`) SHALL install Podman (system and user, lingering enabled for `pilot`), Cockpit with cockpit-podman, and write site values to on-box files under `/etc/infra-core` (not into git). It MUST NOT install a Materia binary, Materia systemd timers, or `/etc/materia` as a required path. It MUST NOT require Docker or Komodo to be present, and MUST NOT require a Docker/Komodo purge to complete.

#### Scenario: Layer 0 without GitOps poller
- **WHEN** `core.sh` finishes on a new OS
- **THEN** `podman` and Cockpit are present, `/etc/infra-core/site.env` exists, and `materia` is not required on `PATH`

### Requirement: Existing ext4 data disk is not formatted
If an extra disk already has an ext4 filesystem, bootstrap SHALL mount and register it as `DATA_ROOT`. It MUST NOT offer format unless there is no ext4 and the operator types `YES`. If a `/srv/dev-disk-by-uuid-*` path is already mounted, that mount SHALL be `DATA_ROOT`.

#### Scenario: Pre-mounted uuid is used
- **WHEN** `/srv/dev-disk-by-uuid-<uuid>` is already a mount of the site data disk
- **THEN** `core.sh` sets `DATA_ROOT` to that path and does not run `mkfs`

### Requirement: Layer 0 stops before apply and before lan-bind
`core.sh` SHALL run thin `data-root-prep` only (not full household `shared/` layout), SHALL leave `core-lan-bind` disabled, SHALL NOT export NFS, and SHALL NOT apply catalog components. Host DNS during Layer 0 SHALL use public resolvers until Pi-hole listens.

#### Scenario: Done message does not enable redirects
- **WHEN** `core.sh` prints Done
- **THEN** `:53`/`:80`/`:443` host REDIRECT is not enabled and NFS exports have not been written by this run

### Requirement: Secret prompts do not steal stdin
Site-secret collection SHALL NOT read the secret list from the same stdin that `read -p` uses for operator prompts. Answers and `site.env` SHALL be written under `/etc/infra-core`. Paths and helpers named for Komodo (`/etc/komodo`, `komodo_*`) MUST NOT be required.

#### Scenario: Prefill answers keep DOMAIN
- **WHEN** `/etc/infra-core/bootstrap-answers.env` already contains `DOMAIN` and `NAS_LAN_IP`
- **THEN** those values appear unchanged in `/etc/infra-core/site.env` after secret collection
