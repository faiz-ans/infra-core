# Windows 11 cutover: Kodi, Firefox, idle mantle

Do this **before** wiping `C:`. Copy onto an external disk or NAS SMB (`Z:`), **not** `C:`. Do **not** format the Restic USB (`D:`); unplug it during setup. Do **not** format the NAS.

This site’s names after cutover:

| Hostname | What |
|---|---|
| `core` | NAS |
| `surface` | Windows 11 TV PC |
| `mantle` | Ubuntu WSL2 on `surface` |

Admin on all three is **`pilot`**. WSL is owned by Windows user **`HTPC`** (not `pilot`). Linux user inside Ubuntu is `pilot`.

## A. Backup (quit Kodi and Firefox first)

| What | Copy this whole folder |
|---|---|
| Kodi (AKL, skins, menus, addons, sources) | `%APPDATA%\Kodi` |
| Firefox (all profiles, including the Kodi web-app profile) | `%APPDATA%\Mozilla\Firefox` |
| Steam→AKL helpers (optional) | `C:\Utils\kodi-akl-steam-installed` |

In Explorer, paste `%APPDATA%` in the address bar. Typical paths:

```text
C:\Users\<you>\AppData\Roaming\Kodi
C:\Users\<you>\AppData\Roaming\Mozilla\Firefox
```

Copy onto e.g. `Z:\htpc-win11-backup\` so you have:

```text
htpc-win11-backup\
  Kodi\
  Firefox\
  kodi-akl-steam-installed\     (optional)
```

Check: `Kodi\userdata\addon_data` exists (AKL lives there). `Firefox\profiles.ini` and `Firefox\Profiles\` exist.

## B. Clean-install Windows 11

1. Uninstall Docker Desktop on Win10 only if you are **not** wiping `C:` (shrinks leftover WSL state).
2. Create a Windows 11 USB with Microsoft Media Creation Tool.
3. Boot the USB. Delete the **Windows** partitions on the **internal** disk only. Leave other disks alone. USB backup should be unplugged.
4. Finish OOBE. Create Windows admin **`pilot`** and daily/WSL user **`HTPC`**. Set the computer name to **`surface`**. If Kodi and Firefox run as `HTPC`, restored `%APPDATA%` is `C:\Users\HTPC\`.
5. Ethernet on `surface` is later pinned to `SURFACE_UPSTREAM` (`bootstrap/surface/surface-lan-static.ps1`). A DHCP lease is fine until that script runs.

## C. Restore Kodi and Firefox

Logged in as the account that runs Kodi (usually `HTPC`):

1. `winget import -i windows\packages.json` **or** install at least `XBMCFoundation.Kodi` and `Mozilla.Firefox`.
2. Quit Kodi and Firefox if the first launch created empty profiles.
3. Copy `htpc-win11-backup\Kodi` → `%APPDATA%\Kodi` (replace the new empty folder).
4. Copy `htpc-win11-backup\Firefox` → `%APPDATA%\Mozilla\Firefox` (replace).
5. Restore `C:\Utils\kodi-akl-steam-installed` if you use it. Map `Z:` to `\\core\shared` (or the NAS SMB name), then re-register the Steam sync task from `windows/steam-akl/`.
6. Open Kodi: AKL, skin, and menus should match. Open Firefox: the Kodi web-app profile should be in `about:profiles`.

## D. Idle WSL (`mantle`, no stacks)

Do this logged in as Windows user **`HTPC`**. Create `C:\Users\HTPC\.wslconfig` (it does not exist until you write it):

```ini
[wsl2]
networkingMode=mirrored
hostAddressLoopback=true
```

Admin is only for `wsl --install --no-distribution` once. Install Ubuntu while logged in as `HTPC`. Linux user `pilot`. In the distro, `/etc/wsl.conf`:

```ini
[boot]
systemd=true
[user]
default=pilot
[network]
hostname=mantle
```

Then `wsl --shutdown`, reopen, and confirm:

- `hostname` is `mantle`
- `wslinfo --networking-mode` is `mirrored`
- `systemctl is-system-running` is `running`

Do **not** install Docker Desktop, Podman Desktop, or Materia stacks yet. Catalog apply on `mantle` comes after Core is on Podman and this repo’s components exist.

USB SMART for Scrutiny: `windows/scrutiny-collector/`. Steam → AKL: `windows/steam-akl/`.
