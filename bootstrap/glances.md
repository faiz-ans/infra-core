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

Runs on **periphery**. Homepage scrapes `http://<HTPC_UPSTREAM>:61208`. On Docker Desktop this is the WSL2 VM (where the stacks run), not `C:`. Glances only lists physical filesystems; inside Docker the VM disk shows up as mount `/etc/hosts` (not `/`). That is the widget path.

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
| Periphery disk missing | Redeploy **glances-periphery** and **homepage**. From Core: `wget -qO- http://<HTPC>:61208/api/4/fs` must include `"mnt_point": "/etc/hosts"`. Widget path is `/etc/hosts`, not `/` |
