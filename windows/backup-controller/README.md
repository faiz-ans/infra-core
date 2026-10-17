# surface USB SMART → Scrutiny

mantle can mount the USB backup volume as a filesystem (`BACKUP_DRIVE` → `/mnt/d`) for Restic REST. It does **not** expose that disk to `smartctl` inside a Linux container. This spoke runs on Windows, talks to the Scrutiny hub on Core (`http://<NAS_LAN_IP>:8087`), and labels disks **surface**.

Hub first-run: [`bootstrap/first-run/scrutiny.md`](../../bootstrap/first-run/scrutiny.md).

## Files

| File | Role |
|---|---|
| [`../backup-controller/install-surface.ps1`](../backup-controller/install-surface.ps1) | Disk on/off, SMART self-tests, and the Scrutiny collect task |
| `Invoke-ScrutinyCollector.ps1` | One collection run (task target) |

Install [smartmontools](https://www.smartmontools.org/) first (`winget install smartmontools.smartmontools`, or `windows/packages.json`).

## surface: one-time setup

Elevated PowerShell, with D: online. This is the same script that registers the backup-disk tasks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-surface.ps1
```

Run it from a copy of `windows/backup-controller` that also contains `Invoke-ScrutinyCollector.ps1` (`install-loadmaster.sh` places that file beside the script). From a repo checkout, the installer finds `windows/scrutiny-collector/Invoke-ScrutinyCollector.ps1` itself.

It downloads the AnalogJ Windows collector into `C:\ProgramData\backup-disk`, writes `collector.yaml`, and registers **BackupDiskCollect**. That task has no schedule. Re-running the installer removes the old **Scrutiny Collector** task. The default endpoint is `http://192.168.1.110:8087` and the host id is **surface**. Pass `-ApiEndpoint` to use another hub.

The backup controller on Core runs the collect after the nightly backup, prune, and any SMART self-test, while the Restic drive is still enabled, then parks the drive. The same run scans the internal SSD. Install the updated `backup-remote` on Mantle and restart the backup controller so the new `collect` command is allowed.

Confirm, while D: is online:

```powershell
& 'C:\Program Files\smartmontools\bin\smartctl.exe' --scan
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProgramData\backup-disk\Invoke-ScrutinyCollector.ps1
```

Then `https://disks.<DOMAIN>` should list the USB disk (and usually the internal NVMe/SSD). Ignore the SSD in the Scrutiny UI if you only care about the backup drive, or set `allow_listed_devices` in `collector.yaml` to the USB’s `smartctl` name after the first scan.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `smartctl binary is missing` | Install smartmontools. Confirm `C:\Program Files\smartmontools\bin\smartctl.exe`. Re-run `install-surface.ps1` so `collector.yaml` has that path |
| USB missing, SSD present | USB asleep / unplugged, or need **elevated** PowerShell. `--scan` must list the USB |
| POST / connection refused | Hub **scrutiny** is Up. Endpoint is `http://<NAS_LAN_IP>:8087` (LAN bind, not a Caddy HTTPS URL) |
| running scripts is disabled | Do not change the machine policy. Launch with `powershell -NoProfile -ExecutionPolicy Bypass -File` |
| Access denied | Task must run as an administrator principal (`RunLevel Highest`) |
