## ADDED Requirements

### Requirement: Linkding on Core with edge proxy
Linkding SHALL deploy on server `core`, attach to the `edge` Docker network, and SHALL NOT publish a host port. Caddy SHALL proxy `links.{$DOMAIN}`, `bookmarks.{$DOMAIN}`, and `linkding.{$DOMAIN}` to the Linkding service by container name on port 9090. Bookmark data SHALL be SQLite under `${DATA_ROOT}/system/linkding`. The initial superuser name and password SHALL come from Komodo (`LINKDING_SUPERUSER_NAME`, `LINKDING_SUPERUSER_PASSWORD`) and MUST NOT be committed in git. `LD_CSRF_TRUSTED_ORIGINS` SHALL include the three HTTPS origins. Caddy MUST NOT apply Authelia forward-auth to these hostnames.

#### Scenario: Bookmarks through Caddy
- **WHEN** a client opens `https://links.{$DOMAIN}`
- **THEN** Caddy on Core proxies to Linkding on the edge network

#### Scenario: Superuser from Komodo
- **WHEN** Linkding starts for the first time with Komodo `LINKDING_SUPERUSER_NAME` and `LINKDING_SUPERUSER_PASSWORD` set
- **THEN** that superuser can log in at `https://links.{$DOMAIN}` and the password is not present in the catalog
