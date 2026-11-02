## MODIFIED Requirements

### Requirement: Greenfield bootstrap order
New-site bring-up SHALL follow: (0) GET Task A from IPs + admin users; (1) operator writes desired topology (roots, roles, users, services, imports); (2) SET; (3) GET A+B into observed; later edits are Day 2 diff+SET. OMV SMB/NFS, ResourceSync, and `data-root-prep` MUST NOT appear in this order.

#### Scenario: Empty disk greenfield
- **WHEN** a site has empty owned roots and desired lists OpenCloud plus site users
- **THEN** SET creates homes and does not require park scripts before the first login

### Requirement: Split host permission scripts
The catalog MUST NOT require separate `data-root-prep` and `data-root-layout` scripts. SET SHALL create roots, homes, and service-specific dirs according to native-storage and official pack rules.

#### Scenario: No prep script on the happy path
- **WHEN** an operator follows the product README
- **THEN** they are not told to run `data-root-prep.sh` or `data-root-layout.sh`

### Requirement: Homepage rollout seed
Homepage tiles SHALL be generated from desired services and the official pack. A committed household Homepage YAML MUST NOT be the default for new sites.

#### Scenario: New site tiles follow desired
- **WHEN** desired lists OpenCloud and Pi-hole and Homepage
- **THEN** generated Homepage config includes those tiles and not a hardcoded Komodo or OMV tile
