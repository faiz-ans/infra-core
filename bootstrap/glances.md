# Glances first-run

Glances feeds Homepage host stats (header widgets and System → Platform tiles). The **web UI** is on Caddy. Homepage still scrapes internally (not through Caddy).

## Core

Runs on **Core** (`edge`). Homepage scrapes `http://glances:61208`. Browser: `https://glances.<DOMAIN>` (alias `glances-core.`). `pid: host` so the numbers are the NAS, not the container. `${DATA_ROOT}` is mounted at `/mnt/data` (the data-disk widget).

No Komodo secret. No new `system/` directory. No LAN port.

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **glances** → **Deploy**. Redeploy **caddy** and **homepage**.

```text
docker ps --filter name=glances --format "table {{.Names}}\t{{.Status}}"
```

You want `glances` **Up**. It must **not** publish 61208 on the LAN.

## Periphery

Runs on **periphery**. Homepage scrapes `http://<HTPC_UPSTREAM>:61208`. Browser: `https://glances2.<DOMAIN>` (alias `glances-htpc.`). CPU/RAM/uptime are the Docker Desktop VM. **Disk is Windows `C:`**, bind-mounted from `/mnt/host/c` to `/mnt/windows` (not the WSL2 VHD). The widget path is `/mnt/windows`.

GPU (RTX 2060) needs the `ubuntu-latest-full` image and NVIDIA in Docker Desktop (Settings → Resources → GPU). Alpine `latest` cannot load NVML. WSL2 usually has no CPU thermal sensors, so Periphery has no CPU-temp tile; GPU temp is on the GPU widget.

Allow Windows Firewall TCP **61208** from the LAN (Caddy and Homepage on Core). See `bootstrap/periphery.md`.

Komodo → **Stacks** → **glances-periphery** → **Deploy**.

```text
docker ps --filter name=glances-periphery --format "table {{.Names}}\t{{.Status}}"
```

## If it fails

| Symptom | What to do |
|---|---|
| Click opens `http://glances:61208` | Redeploy **homepage** (href is `https://glances.<DOMAIN>`). Redeploy **caddy** |
| `glances.<DOMAIN>` does not load | Redeploy **caddy**. Core glances must be Up on `edge`. From Core: `docker exec caddy wget -S -O- --timeout=5 http://glances:61208/ \| head` |
| `glances2.<DOMAIN>` does not load | Windows Firewall **61208**. Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=5 http://<HTPC_UPSTREAM>:61208/ \| head` |
| Core widget empty / API error | Redeploy **homepage**. Then `docker exec homepage wget -S -O- --timeout=5 http://glances:61208/api/4/cpu` |
| Periphery widget empty | Windows Firewall **61208**. From Core: `docker exec homepage wget -S -O- --timeout=5 http://<HTPC_UPSTREAM>:61208/api/4/cpu` |
| API 404 | Image is Glances 4; widgets use `version: 4`. Do not set version 3 |
| Data disk missing on Core | Confirm `/mnt/data` is mounted (`docker exec glances df -h /mnt/data`) |
| Periphery disk is ~800 GB free / looks like the VM | Redeploy **glances-periphery** after this catalog pull. `docker exec glances-periphery df -h /mnt/windows` should match Explorer on `C:`. Widget path is `/mnt/windows`, not `/etc/hosts` |
| Periphery disk missing | `/mnt/host/c` is Docker Desktop’s C: in the engine VM. If the container cannot start, Docker Desktop → Settings → Resources → File sharing must include `C:\`. Then Redeploy **glances-periphery** and **homepage** |
| Core CPU temp is `-` | Sensor label must match Glances exactly. `docker exec glances wget -qO- http://127.0.0.1:61208/api/4/sensors` and set `metric: sensor:<label>` (Pi is usually `cpu_thermal 0`) |
| Periphery GPU is `-` / empty | Redeploy **glances-periphery** after this catalog pull (image change). Docker Desktop GPU on, current NVIDIA Windows driver (WSL). Then `docker exec glances-periphery wget -qO- http://127.0.0.1:61208/api/4/gpu` should list `gpu_id` 0 |
