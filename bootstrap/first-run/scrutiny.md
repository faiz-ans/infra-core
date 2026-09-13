# Scrutiny first-run

Scrutiny is the site disk-SMART dashboard. The **hub** (web + InfluxDB + NAS collector) runs on **Core**. It scans the IronWolf (and any other disks Docker can see on the Pi) every day at 06:00 (`TZ`), and once at container start.

The HTPC USB backup drive is **not** visible as a SCSI device inside Docker Desktop. SMART for that disk is a Windows scheduled collector: [`windows/scrutiny-collector/`](../../windows/scrutiny-collector/README.md).

Caddy is `https://disks.<DOMAIN>` (`scrutiny.` 301 there). Authelia forward-auth is on the vhost (`admins` / **faiz** only). Homepage scrapes `http://scrutiny:8080` on `edge` (not through Caddy).

No Komodo secret.

## 1. Directories (existing Core)

If this site already ran `core.sh` before Scrutiny existed, run `data-root-perms.sh` so `system/scrutiny/{config,influxdb}` exists. Do not re-run bootstrap only for this app.

## 2. Deploy the hub

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **scrutiny** → **Deploy**. Redeploy **authelia**, **caddy**, and **homepage**.

On Core:

```text
docker ps --filter name=scrutiny --format "table {{.Names}}\t{{.Status}}"
lsblk -d -o NAME,TRAN,MODEL,SIZE
```

You want `scrutiny` **Up**. It publishes **8080 on `NAS_LAN_IP` only** (HTPC collector). It must not publish 8080 on the WAN NIC.

Open **`https://disks.<DOMAIN>`**. The IronWolf should appear under host id **core**. The Pi OS mmc/nvme may appear too; that is useful. Ignore loop devices in the UI if they show up.

Trigger a **Short** self-test from the UI when you want an on-demand SMART test. Daily cron is attribute collection (`smartctl -x`), not a long test.

## 3. HTPC USB backup drive

On the HTPC, after `BACKUP_DRIVE` is the USB volume Docker Desktop shares:

1. `winget install smartmontools.smartmontools` (also in `windows/packages.json`).
2. Follow [`windows/scrutiny-collector/README.md`](../../windows/scrutiny-collector/README.md) with `-ApiEndpoint http://<NAS_LAN_IP>:8080`.
3. Run the task once. On `https://disks.<DOMAIN>` the USB disk should show under host id **periphery**.

Do not pass the USB into a Linux collector container: Docker Desktop file-sharing is a filesystem mount, not SMART.

## If it fails

| Symptom | What to do |
|---|---|
| `disks.<DOMAIN>` does not load while `scrutiny` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://scrutiny:8080/api/health` |
| Forbidden / 403 | Authelia `default_policy` is deny. Redeploy **authelia** so `disks.` is in the `admins` gate. Log in as **faiz** |
| Authelia loop / 401 | Log in as **faiz** (or **diana**). Private window to confirm the gate |
| IronWolf missing | `docker exec scrutiny smartctl --scan`. Confirm the SATA disk is `/dev/sdX`, not only the OS mmc. Privileged + `/dev` is required |
| `hdd=0C` on the cage fan | Separate from Scrutiny; see `bootstrap/core/core-fan.md`. `smartctl -A` on the host |
| HTPC USB missing | Collector is the Windows task, not a Komodo stack. `smartctl --scan` in an **elevated** PowerShell. Endpoint must be `http://<NAS_LAN_IP>:8080` |
| Collector cannot POST | From the HTPC: `curl http://<NAS_LAN_IP>:8080/api/health`. Bind is `NAS_LAN_IP:8080`, not `0.0.0.0` |
| Homepage widget empty | Redeploy **homepage**. Then `docker exec homepage wget -S -O- --timeout=5 http://scrutiny:8080/api/summary` |
| Core RAM pressure | Omnibus includes InfluxDB. If the Pi is swapping, stop other Core stacks first; do not move the hub to the HTPC if you still want IronWolf health when Docker Desktop is down |
