## ADDED Requirements

### Requirement: Adventure Log on periphery
Adventure Log SHALL deploy on `periphery` as the official standard (aio) image plus PostGIS. PostgreSQL data and Adventure Log media SHALL be local Docker volumes on the HTPC and MUST NOT use the Docker NFS driver. The stack SHALL publish host port 8015 mapped to the aio HTTP port. Caddy SHALL proxy `travel.{$DOMAIN}`, `adventures.{$DOMAIN}`, and `adventurelog.{$DOMAIN}` to `{$HTPC_UPSTREAM}:8015`. `SITE_URL` SHALL be `https://travel.${DOMAIN}`. `POSTGRES_PASSWORD` and the first-boot Django admin password SHALL come from Komodo and MUST NOT be committed in git. Self-registration SHALL be disabled. Caddy MUST NOT apply Authelia forward-auth to these hostnames.

#### Scenario: Travel log through Caddy
- **WHEN** a client opens `https://travel.{$DOMAIN}`
- **THEN** Caddy on Core proxies to Adventure Log’s published port on `HTPC_UPSTREAM`

#### Scenario: Admin from Komodo
- **WHEN** Adventure Log starts for the first time with Komodo admin and database secrets set
- **THEN** that Django admin can sign in at `https://travel.{$DOMAIN}` and open registration is disabled
