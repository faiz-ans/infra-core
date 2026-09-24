## ADDED Requirements

### Requirement: Collabora on periphery for OpenCloud WOPI
Collabora Online SHALL deploy on `periphery` and SHALL publish port 9980. Caddy SHALL proxy `office.{$DOMAIN}` (and `collabora.` alias) to `{$HTPC_UPSTREAM}:9980` without Authelia forward-auth. OpenCloud on `core` SHALL enable the in-process collaboration service with WOPI source `https://cloud.{$DOMAIN}` and Collabora app address `https://office.{$DOMAIN}`. Collabora SHALL allow the OpenCloud origin as `aliasgroup1`. TLS between Caddy and Collabora SHALL be HTTP with SSL termination at Caddy (`ssl.enable=false`).

#### Scenario: Office hostname
- **WHEN** a client opens `https://office.{$DOMAIN}`
- **THEN** Caddy on `nas` proxies to Collabora on `HTPC_UPSTREAM:9980`

#### Scenario: OpenCloud points at Collabora
- **WHEN** OpenCloud is deployed with collaboration enabled
- **THEN** its collaboration app address is `https://office.{$DOMAIN}` and WOPI is served on the OpenCloud public URL
