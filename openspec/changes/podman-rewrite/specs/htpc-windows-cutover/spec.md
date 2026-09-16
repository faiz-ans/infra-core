## ADDED Requirements

### Requirement: Backup Kodi userdata before wipe
The catalog SHALL document copying the entire `%APPDATA%\Kodi` folder (userdata, addons, AKL `addon_data`, skins, menu layout) to removable media or NAS SMB (`Z:`), not to `C:`. The backup MUST be taken while Kodi is quit.

#### Scenario: AKL and skin survive
- **WHEN** the operator copies `%APPDATA%\Kodi` to the backup location and later restores it over a new Kodi install
- **THEN** AKL sources, skin, and home menu layout are present without reinstalling addons from scratch

### Requirement: Backup Firefox profiles before wipe
The catalog SHALL document copying the entire `%APPDATA%\Mozilla\Firefox` folder (`profiles.ini`, `Profiles\`, including the profile used when Kodi launches web apps) to the same backup location, with Firefox quit.

#### Scenario: Web-app profile restored
- **WHEN** the operator restores `%APPDATA%\Mozilla\Firefox` before or immediately after installing Firefox, replacing any empty default profile
- **THEN** Firefox `about:profiles` still lists the Kodi web-app profile and that profile’s data is intact

### Requirement: Clean-install Windows 11 wiping C:
The catalog SHALL instruct a Media Creation Tool USB install that deletes Windows partitions on the **internal** system disk only. It MUST tell the operator not to format the NAS, not to format the Restic USB (unplug it during setup), and to uninstall Docker Desktop only if they are not wiping `C:`.

#### Scenario: Wrong disk is not selected
- **WHEN** the operator follows the disk-selection steps
- **THEN** only the `surface` Windows disk is wiped and `BACKUP_DRIVE` / NAS content is not targeted

### Requirement: Restore then idle mantle
After OOBE, the catalog SHALL instruct creating Windows admin **`pilot`** and daily/WSL user **`HTPC`**, setting the computer name to **`surface`**, installing Kodi and Firefox (winget), restoring the two Roaming folders (and optional `C:\Utils\kodi-akl-steam-installed`), remapping `Z:` if used, then installing Ubuntu WSL as `HTPC` with Linux user **`pilot`**, `C:\Users\HTPC\.wslconfig` (mirrored networking), and `/etc/wsl.conf` hostname **`mantle`** plus systemd, **without** deploying catalog stacks or Docker/Podman Desktop.

#### Scenario: Idle mantle after restore
- **WHEN** the cutover steps are complete
- **THEN** Kodi and Firefox work from the restored data, `hostname` in the distro is `mantle`, `wslinfo --networking-mode` is `mirrored`, `systemctl is-system-running` is `running`, and no mantle catalog Quadlets are required yet
