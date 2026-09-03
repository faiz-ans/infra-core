# Glances first-run

Glances feeds Homepage host stats on the **System** tab (CPU, memory, disk). It is not behind Caddy. The global header does not show host stats.

## Core

Runs on **Core** (`edge`). Homepage scrapes `http://glances:61208`. `pid: host` so the numbers are the NAS, not the container. `${DATA_ROOT}` is mounted at `/mnt/data` (the data-disk widget).

No Komodo secret. No new `system/` directory.

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **glances** → **Deploy**. Redeploy **homepage** so the System → Hosts widgets exist.

```text
docker ps --filter name=glances --format "table {{.Names}}\t{{.Status}}"
```

You want `glances` **Up**. It must **not** publish 61208 on the LAN.

## Periphery

Runs on **periphery**. Homepage scrapes `http://<HTPC_UPSTREAM>:61208`. CPU/RAM are the Docker Desktop VM. **Disk is Windows `C:`**, bind-mounted from `/mnt/host/c` to `/mnt/windows` (not the WSL2 VHD). The widget path is `/mnt/windows`.

Allow Windows Firewall TCP **61208** from the LAN (Homepage on Core). See `bootstrap/periphery.md`.

Komodo → **Stacks** → **glances-periphery** → **Deploy**.

```text
docker ps --filter name=glances-periphery --format "table {{.Names}}\t{{.Status}}"
```

## If it fails

| Symptom | What to do |
|---|---|
| Core widget empty / API error | Redeploy **homepage**. Then `docker exec homepage wget -S -O- --timeout=5 http://glances:61208/api/4/cpu` |
| Periphery widget empty | Windows Firewall **61208**. From Core: `docker exec homepage wget -S -O- --timeout=5 http://<HTPC_UPSTREAM>:61208/api/4/cpu` |
| API 404 | Image is Glances 4; widgets use `version: 4`. Do not set version 3 |
| Data disk missing on Core | Confirm `/mnt/data` is mounted (`docker exec glances df -h /mnt/data`) |
| Periphery disk is ~800 GB free / looks like the VM | Redeploy **glances-periphery** after this catalog pull. `docker exec glances-periphery df -h /mnt/windows` should match Explorer on `C:`. Widget path is `/mnt/windows`, not `/etc/hosts` |
| Periphery disk missing | `/mnt/host/c` is Docker Desktop’s C: in the engine VM. If the container cannot start, Docker Desktop → Settings → Resources → File sharing must include `C:\`. Then Redeploy **glances-periphery** and **homepage** |
