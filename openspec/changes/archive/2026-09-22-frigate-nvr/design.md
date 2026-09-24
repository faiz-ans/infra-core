## Context

Core is a 4GB NAS with Caddy on `edge`. Periphery is Docker Desktop (WSL2). HTPC media stacks already use `compose.nfs.yaml` for household data and a local volume for `/config`. ZoneMinder was trialled and removed. Household-services explicitly deferred an NVR. Docker Desktop factory pools overlapping `192.168.0.0/16` is already a Layer 0 step.

Frigate’s official image creates a config and an admin password in logs if `/config` is empty. Reverse-proxying 8971 requires `tls.enabled: false`. The Home Assistant integration needs a shared MQTT broker. Camera RTSP URLs are site-specific and must not live in git.

## Goals / Non-Goals

**Goals:**

- Frigate is a GitOps stack on `periphery` with Caddy hostnames and a Homepage tile.
- Recordings land on `${DATA_ROOT}/shared/cameras` (this site: NFS). Config/SQLite stay local.
- MQTT is available to Frigate and Home Assistant without a separate ResourceSync stack.
- Off-LAN NVR access is wg-easy only. No new router forwards.

**Non-Goals:**

- Authelia forward-auth on Frigate hostnames (Frigate’s own login on 8971).
- Coral, OpenVINO, CUDA, `/dev/dri`, USB passthrough, `privileged: true`.
- Frigate+ / `PLUS_API_KEY`.
- Publishing port 5000 (unauthenticated API) on the host.
- Cataloguing camera RTSP URLs or passwords.
- Migrating `DATA_ROOT` onto the IronWolf.

## Decisions

### 1. Placement: periphery, not Core

Frigate decodes streams and runs a CPU detector. Core RAM is already tight. Same placement as the dropped ZoneMinder trial and as Scriberr.

**Alternative considered:** Frigate on Core so the NVR stays up when the HTPC sleeps. Rejected: 4GB NAS plus object detection is not viable. The HTPC is the always-on decode host for this catalog.

### 2. Storage split: local `/config`, NFS `/media/frigate`, tmpfs cache

| Path | Where | Why |
|---|---|---|
| `/config` | named volume `frigate-config` | SQLite and site `config.yml`; survives Core/NFS down; Docker Desktop must not bind a single file |
| `/media/frigate` | `shared/cameras` via `compose.yaml` bind or `compose.nfs.yaml` NFS | Recordings/clips/exports are large household data |
| `/tmp/cache` | tmpfs 1GB | Frigate requires fast local segments before they move to media |

This site’s ResourceSync uses `compose.nfs.yaml` (`NAS_LAN_IP`, `NFS_EXPORT=/shared`, device `:${NFS_EXPORT}/cameras`). `compose.yaml` exists for a host-mounted `DATA_ROOT`. Do not list both files.

**Alternative considered:** All Frigate data on local HTPC volumes. Rejected: recordings would not live on the NAS tree that restic/IronWolf will back up.

**Alternative considered:** SQLite on NFS. Rejected: Frigate keeps the database under `/config`.

### 3. Seed config, then UI editor — not Komodo `config_files`

Bind-mounting `config.yml` from git would overwrite cameras on every ResourceSync. Docker Desktop also drops single-file binds.

Mount `./seed` as a directory. On start, if neither `config.yml` nor `config.yaml` exists in the volume, copy the seed. Seed sets `tls.enabled: false`, MQTT to sidecar `mosquitto`, CPU detector, empty `cameras`. After first copy, the operator adds cameras in Frigate’s config editor. Later catalog pulls do not touch the volume file.

Admin password is printed in `docker logs frigate` on first start (same as upstream). No Komodo secret.

**Alternative considered:** Empty volume and let Frigate generate a default. Rejected: generated TLS on 8971 breaks Caddy (`400` plain HTTP to HTTPS port), and MQTT would stay off until someone edits YAML.

### 4. Mosquitto sidecar, anonymous on LAN 1883

`eclipse-mosquitto:2` in the Frigate compose project so Frigate can use hostname `mosquitto`. Publish `1883:1883` for Home Assistant (different Compose project). Mosquitto config is a directory bind (`listener 1883`, `allow_anonymous true`). Caddy MUST NOT proxy MQTT. Windows firewall: LAN only.

HA MQTT integration: broker = `HTPC_UPSTREAM` (or `host.docker.internal` from the HA container). Frigate integration after MQTT works.

**Alternative considered:** No broker until someone wants HA. Rejected: this catalog already has Home Assistant; MQTT is the documented requirement for that integration.

**Alternative considered:** MQTT credentials as Komodo secrets. Rejected: extra password-file machinery for a LAN-only broker behind the existing firewall table. Operators can tighten later in the volume.

### 5. Ports and Caddy

Publish:

| Host | Use |
|---|---|
| `8971` | Authenticated UI/API — Caddy upstream |
| `8554` | go2rtc RTSP restream (LAN) |
| `8555/tcp` + `8555/udp` | WebRTC |
| `1883` | MQTT |

Do **not** publish `5000`. Caddy: `cams.` `nvr.` `frigate.` → `{$HTPC_UPSTREAM}:8971` with long timeouts and `flush_interval -1` for live view. No `authelia_gate`. WebRTC candidates stay on the LAN/VPN; do not stream 8555 through Caddy.

`shm_size: "256mb"`. `stop_grace_period: 30s`. Image `ghcr.io/blakeblackshear/frigate:stable`. No `devices:` and not privileged.

### 6. Homepage

Apps → Local, next to Home Assistant. `href` through Caddy, `server: periphery`, `container: frigate`. No API widget (would need 5000 or Frigate login keys).

## Risks / Trade-offs

- **[CPU detector on Docker Desktop is slow / drops frames]** → First-run: start with one camera, low detect resolution. Coral/GPU remain operator-optional, not catalogued.
- **[1GB tmpfs on an 8GB HTPC]** → Official default; if the box OOMs, lower tmpfs in compose (site edit) rather than putting cache on NFS.
- **[Anonymous MQTT on 1883]** → Firewall LAN-only; not on Caddy; not on the WAN. Same exposure class as other published HTPC ports.
- **[NFS + recordings]** → Cache is tmpfs; media is NFS with `no_root_squash` already required for other stacks.
- **[HTPC off = no NVR]** → Accepted with placement on periphery.
- **[Seed already copied with TLS on, from a manual trial]** → First-run: if Caddy gets 400, set `tls.enabled: false` in the volume and restart.

## Migration Plan

1. Run `data-root-perms.sh` (creates `shared/cameras`). Existing Core: do not re-run `core.sh` only for this.
2. Push catalog; ResourceSync; Deploy **frigate**; Redeploy **caddy** and **homepage**. Windows firewall 8971, 8554, 8555 tcp/udp, 1883 from the LAN.
3. `docker logs frigate` for the admin password. Open `https://cams.<DOMAIN>`. Add cameras in the UI. Point HA MQTT at `HTPC_UPSTREAM:1883`, then add the Frigate integration.
4. Rollback: `deploy = false` or remove the stack. Named volume `frigate-config` and `shared/cameras` are left unless the operator deletes them.

## Open Questions

- None.
