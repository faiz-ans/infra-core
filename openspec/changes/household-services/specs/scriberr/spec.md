## ADDED Requirements

### Requirement: Scriberr on periphery
Scriberr SHALL deploy on `periphery` via ResourceSync using the official CPU image. SQLite, uploads, transcripts, and the Whisper/Python environment SHALL be local Docker volumes on the HTPC and MUST NOT use the Docker NFS driver. The stack SHALL publish host port 8085 mapped to container port 8080. Caddy SHALL proxy `scribe.{$DOMAIN}`, `transcribe.{$DOMAIN}`, and `scriberr.{$DOMAIN}` to `{$HTPC_UPSTREAM}:8085` with long read/write timeouts for audio uploads. `ALLOWED_ORIGINS` SHALL list those three HTTPS origins. `APP_ENV` SHALL be `production`. Caddy MUST NOT apply Authelia forward-auth to these hostnames. CUDA/GPU images are out of scope.

#### Scenario: Transcribe through Caddy
- **WHEN** a client opens `https://scribe.{$DOMAIN}`
- **THEN** Caddy on Core proxies to Scriberr’s published port on `HTPC_UPSTREAM`

#### Scenario: Models stay local
- **WHEN** Scriberr is deployed
- **THEN** the Whisper/Python volume is on the HTPC engine and is not an NFS volume of `shared/` or `users/`
