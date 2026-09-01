## 1. Periphery stack

- [x] 1.1 Add Frigate compose + NFS variant (stable image, Mosquitto sidecar, shm/tmpfs, ports 8971/8554/8555/1883, no 5000)
- [x] 1.2 Add seed config (tls off, MQTT host mosquitto) copied only when the config volume is empty
- [x] 1.3 Register `frigate` in `stacks-periphery.toml` with `compose.nfs.yaml`

## 2. Edge, Homepage, storage

- [x] 2.1 Caddyfile: `cams.` / `nvr.` / `frigate.` → `{$HTPC_UPSTREAM}:8971` with long timeouts; no Authelia gate
- [x] 2.2 Homepage tile for Frigate (Apps → Local)
- [x] 2.3 Create `shared/cameras` in `data-root-perms.sh` / `core.sh`; document keys in `VARIABLES.md`

## 3. First-run

- [x] 3.1 Add `bootstrap/frigate.md`; firewall ports in `periphery.md`; point README / `omv-nfs.md` at cameras
