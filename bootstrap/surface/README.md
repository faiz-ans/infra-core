# surface (Windows 11 TV PC)

Admin: `pilot`. Daily/WSL owner: Windows user `HTPC`. Computer name: `surface`. Ethernet IPv4 is `SURFACE_UPSTREAM`.

- Pin Ethernet: `surface-lan-static.ps1` (elevated, on the console, cable plugged in).
- USB backup disk: `surface-backup-drive.ps1` (letter `D:` → WSL `/mnt/d`).
- Kodi/Firefox cutover: [`windows/kodi-firefox-cutover.md`](../../windows/kodi-firefox-cutover.md)
- Winget: [`windows/packages.json`](../../windows/packages.json) (no Docker Desktop)

Container engine is **mantle** (Ubuntu WSL2), not this Windows user session. See [`../mantle/README.md`](../mantle/README.md).
