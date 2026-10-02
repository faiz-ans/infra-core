# Windows HTPC

GET/SET (`ansible/site.py`) does not drive this tree. WSL Pi-hole's LAN port 53
is an operator step on the Windows host: [`wsl-pihole.md`](wsl-pihole.md).

Winget list: [`packages.json`](packages.json) (no Docker Desktop).

- **WSL Pi-hole on the LAN:** [`wsl-pihole.md`](wsl-pihole.md)
- **Win11 cutover (Kodi + Firefox + idle `mantle`):** [`kodi-firefox-cutover.md`](kodi-firefox-cutover.md)
- **Steam → AKL (installed games only):** [`steam-akl/README.md`](steam-akl/README.md)
- **USB SMART → Scrutiny on Core:** [`scrutiny-collector/README.md`](scrutiny-collector/README.md)

Optional: ePSXe has no reliable official winget id. Install manually later if needed.

Retired WSL/Ethernet notes live under [`archive/bootstrap/`](../archive/bootstrap/).
