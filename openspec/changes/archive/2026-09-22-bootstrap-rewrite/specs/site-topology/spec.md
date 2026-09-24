## ADDED Requirements

### Requirement: Declarative site topology

The catalog SHALL provide a declarative topology document that lists Komodo server names and assigns each catalog stack to a server, marks it excluded, or (where needed) declares multiple named instances of the same catalog service. Each enabled stack SHALL declare a deploy phase of `bootstrap` or `full`. Where the catalog already distinguishes bind vs NFS compose files, the topology SHALL record which compose flavor to emit. Secrets, LAN IPs, and live domain values MUST NOT appear in the topology file.

#### Scenario: Two-host reference site

- **WHEN** the topology encodes servers `core` and `periphery` with this site’s current stack placements
- **THEN** phase `bootstrap` includes at least caddy, authelia, pihole (core), homepage, opencloud, and collabora (on its assigned server), and phase `full` retains the remaining enabled stacks on their current servers

### Requirement: ResourceSync TOML generation

The catalog SHALL provide a generator that reads the topology and writes committed ResourceSync TOML: a file named `stacks-bootstrap.toml` containing all phase-`bootstrap` stacks (each with the correct literal `server`), plus per-server TOML files for phase-`full` stacks. Generated stack `name` values MUST remain unique across files. Hand-maintained divergence from generator output is unsupported; operators SHALL edit topology and regenerate.

#### Scenario: Generate for reference topology

- **WHEN** an operator runs the generator against this site’s topology
- **THEN** `stacks-bootstrap.toml` exists and phase-B `stacks-core.toml` / `stacks-periphery.toml` (or equivalent per-server names) omit stacks already emitted in bootstrap, without reshuffling non-bootstrap server assignments relative to the prior hand-written split
