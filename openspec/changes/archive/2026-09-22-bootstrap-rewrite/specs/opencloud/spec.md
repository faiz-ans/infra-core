## ADDED Requirements

### Requirement: Greenfield-first OpenCloud documentation

OpenCloud first-run documentation SHALL present the greenfield order (prep, phase-A deploy, login-created homes, Space `shared`, publish bind, layout perms, then phase-full stacks) as the default happy path. Park/restore adopt scripts SHALL be documented as utilities for sites that already have homes or `shared/` content. The readiness check SHALL remain the verification step after layout.

#### Scenario: Doc order for empty site

- **WHEN** an operator follows `bootstrap/opencloud.md` on a disk without pre-created space roots
- **THEN** the primary steps do not require park before first login or before creating Space `shared`
