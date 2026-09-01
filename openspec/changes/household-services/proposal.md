## Why

The site has files, photos, media, passwords, and home automation, but not notes, bookmarks, remote desktop, a travel log, or local transcription. The IronWolf is here; these apps should land on the current `DATA_ROOT` before that disk move so they migrate with everything else.

## What Changes

- Add **Jotty** on `core` (edge): notes and checklists at `notes.{$DOMAIN}`.
- Add **Linkding** on `core` (edge): bookmarks at `links.{$DOMAIN}`.
- Add **RustDesk** OSS (`hbbs`/`hbbr`) on `core` with host networking. ID/relay listen on the NAS LAN only. **No router port-forward** of 21115–21119. Off-LAN desktop access is WireGuard first, same as every other LAN service. Caddy does not proxy the RustDesk protocol.
- Add **Adventure Log** on `periphery`: travel tracker at `travel.{$DOMAIN}`. PostGIS and media on local HTPC volumes.
- Add **Scriberr** on `periphery`: local audio transcription at `scribe.{$DOMAIN}`. Whisper models on HTPC volumes, not NFS.
- Do **not** catalog ZoneMinder (dropped after a trial deploy).
- Homepage tiles, Komodo ResourceSync entries, bootstrap dirs/secrets, and first-run notes. Authelia OIDC for these apps is out of scope (edge gate is still off).

## Capabilities

### New Capabilities

- `jotty`: Jotty on Core, Caddy `notes.` / `jotty.`, state under `${DATA_ROOT}/system/jotty`.
- `linkding`: Linkding on Core, Caddy `links.` / `bookmarks.` / `linkding.`, SQLite under `${DATA_ROOT}/system/linkding`.
- `rustdesk`: OSS ID/relay on Core host network. No public ports. Clients use `desk.{$DOMAIN}` (Pi-hole → `NAS_LAN_IP`) on LAN or after wg-easy.
- `adventurelog`: Adventure Log on periphery, Caddy `travel.` / `adventures.` / `adventurelog.`.
- `scriberr`: Scriberr on periphery, Caddy `scribe.` / `transcribe.` / `scriberr.`, local Whisper volumes.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs yet)

## Impact

- Add `stacks/workload/{jotty,linkding,rustdesk,adventurelog,scriberr}/`.
- `stacks/komodo/stacks-core.toml`, `stacks-periphery.toml`, `VARIABLES.md`.
- `stacks/platform/caddy/Caddyfile`, Homepage `services.yaml`.
- `bootstrap/data-root-perms.sh`, `core.sh`, `periphery.md`, `README.md`, `omv-nfs.md`.
- First-run: `bootstrap/{jotty,linkding,rustdesk,adventurelog,scriberr}.md`.
- Runtime: Core containers `jotty`, `linkding`, `hbbs`, `hbbr`; HTPC stacks `adventurelog` and `scriberr`.
- Router: still UDP 51820 only. Do not forward RustDesk ports.
