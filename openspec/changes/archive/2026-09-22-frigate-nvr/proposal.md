## Why

The site has Home Assistant and cameras, but no NVR after ZoneMinder was dropped. Periphery’s Docker LAN overlap is fixed, so an NVR can land on the HTPC without blocking Komodo.

## What Changes

- Add **Frigate** on `periphery`: CPU detector, official `stable` image, authenticated UI at `cams.{$DOMAIN}`.
- Sidecar **Mosquitto** in the same stack so Home Assistant can use the Frigate integration (MQTT is required for that). MQTT is LAN-only; Caddy does not proxy it.
- Recordings, clips, and exports on NAS `shared/cameras` (this site: Docker NFS). `/config` and SQLite stay a local HTPC volume. `/tmp/cache` is tmpfs.
- Seed `tls.enabled: false` and MQTT host `mosquitto` only when `/config/config.yml` is missing. Camera RTSP URLs stay in that volume (UI editor), not git.
- Homepage tile, ResourceSync, `shared/cameras` bootstrap, first-run notes. Authelia forward-auth is out of scope.
- Coral, OpenVINO, CUDA, and Frigate+ are out of scope (Docker Desktop GPU/USB passthrough).

## Capabilities

### New Capabilities

- `frigate`: Frigate NVR on periphery, Caddy `cams.` / `nvr.` / `frigate.`, media on `shared/cameras`, MQTT sidecar for Home Assistant.

### Modified Capabilities

- (none — `openspec/specs/` has no main specs yet)

## Impact

- Add `stacks/workload/frigate/` (`compose.yaml`, `compose.nfs.yaml`, seed config, Mosquitto conf).
- `stacks/komodo/stacks-periphery.toml`, `VARIABLES.md`.
- `stacks/platform/caddy/Caddyfile`, Homepage `services.yaml`.
- `bootstrap/data-root-perms.sh`, `core.sh`, `periphery.md`, `README.md`, `omv-nfs.md`.
- First-run: `bootstrap/frigate.md`.
- Runtime: HTPC containers `frigate` and `mosquitto`; host ports 8971 (UI), 8554 (RTSP restream), 8555 tcp/udp (WebRTC), 1883 (MQTT).
- Router: still UDP 51820 only. Do not forward Frigate or MQTT ports.
