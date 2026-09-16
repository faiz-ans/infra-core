## ADDED Requirements

### Requirement: Winget list without Docker Desktop
`windows/packages.json` SHALL list intended apps on `surface` (Kodi, AutoHotkey, Firefox, Steam, Dolphin, PCSX2, smartmontools as today) and MUST NOT include `Docker.DockerDesktop`. This change SHALL NOT implement Playnite retirement or Kodi-as-launcher redesign beyond restore of existing userdata.

#### Scenario: Import has no Desktop
- **WHEN** an operator runs `winget import` against the catalog `packages.json` on Windows 11
- **THEN** Docker Desktop is not one of the packages to install

### Requirement: Cutover doc in windows/
`windows/kodi-firefox-cutover.md` SHALL exist and SHALL contain the backup, wipe-install, restore, identities (`pilot` / `HTPC`), and idle-`mantle` steps for Kodi `%APPDATA%\Kodi` and Firefox `%APPDATA%\Mozilla\Firefox`. `windows/README.md` SHALL point at that doc, steam-akl, and scrutiny-collector. `windows/docker-engine.json` MUST NOT remain in the catalog.

#### Scenario: README points at cutover
- **WHEN** an operator opens `windows/README.md`
- **THEN** they are directed to the Kodi/Firefox cutover document and not to Docker Desktop engine JSON
