# Glances first-run

Glances feeds Homepage host stats (header widgets and System → Platform tiles). The **web UI** is on Caddy and is Authelia forward-auth (`admins` / **faiz** only). Homepage still scrapes internally (not through Caddy).

## Core

Runs on **Core** (`edge`). Homepage scrapes `http://glances:61208`. Browser: `https://host.<DOMAIN>` (alias `glances.` / `glances-core.`). `pid: host` so the numbers are the NAS, not the container. `${DATA_ROOT}` is mounted at `/mnt/data` (the data-disk widget).

No attribute. No new `system/` directory. No LAN port.

Re-apply with `apply.sh` **caddy** and **homepage**.

```text
podman ps --filter name=glances --format "table {{.Names}}\t{{.Status}}"
```

You want `glances` **Up**. It must **not** publish 61208 on the LAN.

## Mantle

Runs on **mantle**. Homepage scrapes `http://<SURFACE_UPSTREAM>:61208`. Browser: `https://host2.<DOMAIN>` (alias `glances2.` / `glances-mantle.`). CPU/RAM/uptime are the WSL Podman VM. **Disk is Windows `C:`**, bind-mounted from `/mnt/host/c` to `/mnt/windows` (not the WSL2 VHD). The widget path is `/mnt/windows`.

GPU (RTX 2060) needs the `ubuntu-latest-full` image and NVIDIA in WSL Podman (Settings → Resources → GPU). Alpine `latest` cannot load NVML. WSL2 usually has no CPU thermal sensors, so mantle has no CPU-temp tile; GPU temp is on the GPU widget.

Allow Windows Firewall TCP **61208** from the LAN (Caddy and Homepage on Core). See `bootstrap/mantle/README.md`.

Apply with `sudo bash bootstrap/apply.sh`.

```text
podman ps --filter name=glances-mantle --format "table {{.Names}}\t{{.Status}}"
```

## If it fails

| Symptom | What to do |
|---|---|
| Click opens `http://glances:61208` | re-apply (apply.sh / systemd) **homepage** (href is `https://host.<DOMAIN>`). re-apply (apply.sh / systemd) **caddy** |
| `host.<DOMAIN>` does not load | re-apply (apply.sh / systemd) **caddy**. Core glances must be Up on `edge`. From Core: `podman exec caddy wget -S -O- --timeout=5 http://glances:61208/ \| head` |
| `host2.<DOMAIN>` does not load | Windows Firewall **61208**. re-apply (apply.sh / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=5 http://<SURFACE_UPSTREAM>:61208/ \| head` |
| `glances.service` failed on apply, then Up | kube-play race. `apply.sh` retries the user unit once. If still down: `systemctl --user restart glances.service` |
| Core widget empty / API error | re-apply (apply.sh / systemd) **homepage**. Then `podman exec homepage wget -S -O- --timeout=5 http://glances:61208/api/4/cpu` |
| mantle widget empty | Windows Firewall **61208**. From Core: `podman exec homepage wget -S -O- --timeout=5 http://<SURFACE_UPSTREAM>:61208/api/4/cpu` |
| API 404 | Image is Glances 4; widgets use `version: 4`. Do not set version 3 |
| Data disk missing on Core | Confirm `/mnt/data` is mounted (`podman exec glances df -h /mnt/data`) |
| mantle disk is ~800 GB free / looks like the VM | re-apply (apply.sh / systemd) **glances-mantle** after this catalog pull. `podman exec glances-mantle df -h /mnt/windows` should match Explorer on `C:`. Widget path is `/mnt/windows`, not `/etc/hosts` |
| mantle disk missing | `/mnt/host/c` is WSL Podman’s C: in the engine VM. If the container cannot start, WSL Podman → Settings → Resources → File sharing must include `C:\`. Then re-apply (apply.sh / systemd) **glances-mantle** and **homepage** |
| Core CPU temp is `-` | Sensor label must match Glances exactly. `podman exec glances wget -qO- http://127.0.0.1:61208/api/4/sensors` and set `metric: sensor:<label>` (Pi is usually `cpu_thermal 0`) |
| mantle GPU is `-` / empty | re-apply (apply.sh / systemd) **glances-mantle** after this catalog pull (image change). WSL Podman GPU on, current NVIDIA Windows driver (WSL). Then `podman exec glances-mantle wget -qO- http://127.0.0.1:61208/api/4/gpu` should list `gpu_id` 0 |
