# surface USB SMART → Scrutiny

mantle can mount the USB backup volume as a filesystem (`BACKUP_DRIVE` → `/mnt/d`) for Restic REST. It does **not** expose that disk to `smartctl` inside a Linux container. This spoke runs on Windows, talks to the Scrutiny hub on Core (`http://<NAS_LAN_IP>:8080`), and labels disks **surface**.

Hub first-run: [`bootstrap/first-run/scrutiny.md`](../../bootstrap/first-run/scrutiny.md).

## Files

| File | Role |
|---|---|
| `Install-ScrutinyCollector.ps1` | Download collector, write `collector.yaml`, register the daily task |
| `Invoke-ScrutinyCollector.ps1` | One collection run (task target) |

Install [smartmontools](https://www.smartmontools.org/) first (`winget install smartmontools.smartmontools`, or `windows/packages.json`).

## surface: one-time setup

Elevated PowerShell (smartctl and the task need admin to see physical disks):

```powershell
cd C:\Utils\scrutiny-collector   # copy this directory somewhere local
.\Install-ScrutinyCollector.ps1 -ApiEndpoint 'http://<NAS_LAN_IP>:8080'
Start-ScheduledTask -TaskName 'Scrutiny Collector'
```

Use this site’s `NAS_LAN_IP`. The installer puts the AnalogJ Windows collector and `collector.yaml` next to the scripts.

Task Scheduler → **Scrutiny Collector**: daily 06:15 (after the Core hub’s 06:00 cron) and at startup (+2 min). Host id is **surface**.

Confirm:

```powershell
& 'C:\Program Files\smartmontools\bin\smartctl.exe' --scan
.\Invoke-ScrutinyCollector.ps1
```

Then `https://disks.<DOMAIN>` should list the USB disk (and usually the internal NVMe/SSD). Ignore the SSD in the Scrutiny UI if you only care about the backup drive, or set `allow_listed_devices` in `collector.yaml` to the USB’s `smartctl` name after the first scan.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `smartctl binary is missing` | Install smartmontools. Confirm `C:\Program Files\smartmontools\bin\smartctl.exe`. Re-run the installer so `collector.yaml` has that path |
| USB missing, SSD present | USB asleep / unplugged, or need **elevated** PowerShell. `--scan` must list the USB |
| POST / connection refused | Hub **scrutiny** is Up. Endpoint is `http://<NAS_LAN_IP>:8080` (LAN bind, not a Caddy HTTPS URL) |
| Access denied | Task must run as an administrator principal (`RunLevel Highest`) |
