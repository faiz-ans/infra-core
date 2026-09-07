# Steam → AKL (installed games only)

Steam’s AKL Web API scanner lists everything you **own**. These scripts list what is **installed on this HTPC**, write named `.cmd` launchers, and leave AKL’s default file scanner to pick them up.

```
Steam libraries (C: + Z:\games\steam\…)
        │  appmanifest_*.acf
        ▼
Sync-SteamInstalled.ps1   (Task Scheduler: logon + hourly)
        │
        ▼
Z:\games\steam-installed\<Game Name>.cmd
        │
        ▼
AKL Source (default scanner, ext cmd)
  assets: Z:\games\assets\source\steam
  launcher: directly execute .cmd  (or cmd.exe /c "$ROM$")
```

## Files

| File | Role |
|---|---|
| `Sync-SteamInstalled.ps1` | Build/refresh the `.cmd` folder from local `appmanifest_*.acf` |
| `Register-SteamInstalledTask.ps1` | Create the Scheduled Task |

Defaults assume the NAS games tree is mapped as `Z:` and Steam’s extra library is under `Z:\games\steam`. Override with `-OutputDir` / `-SteamRoot` if yours differ.

| Path | Role |
|---|---|
| `Z:\games\steam-installed` | Sync output / AKL source (`.cmd` launch scripts) |
| `Z:\games\assets\source\steam` | Existing AKL artwork folder (reuse; do not create a second assets tree) |

## HTPC: one-time setup

1. Map `\\<nas>\shared` as persistent **`Z:`** (same user that runs Kodi).
2. Create `Z:\games\steam-installed` if missing. Keep using `Z:\games\assets\source\steam` for scraped art.
3. Copy this directory somewhere local and durable, e.g.  
   `C:\Utils\kodi-akl-steam-installed\`  
   (Do not run the sync script only from a network share if the share can be offline at logon.)
4. Open **PowerShell** (normal user is fine):

```powershell
cd C:\Utils\kodi-akl-steam-installed
.\Sync-SteamInstalled.ps1 -OutputDir '\\CORE\shared\games\steam-installed' -Verbose
```

Confirm `Z:\games\steam-installed` (same folder) fills with named `.cmd` files. Spot-check one in Explorer (double-click should open Steam / the game).

5. Register the task (prefer UNC so the task does not depend on `Z:`):

```powershell
.\Register-SteamInstalledTask.ps1 `
  -ScriptPath C:\Utils\kodi-akl-steam-installed\Sync-SteamInstalled.ps1 `
  -OutputDir '\\CORE\shared\games\steam-installed'
Start-ScheduledTask -TaskName 'AKL Steam Installed Sync'
```

Task Scheduler → Library → **AKL Steam Installed Sync**: logon (+2 min delay) and every hour.

## Kodi / AKL

1. If you already have a **Steam Library** (Web API) source that shows the whole account, remove it or stop using it on the home screen. Rescanning that source will not filter to installed-only.
2. Keep **script.akl.steam** installed if you want its Steam art scraper / launcher helpers; you do not need it as the *scanner* for this path.
3. In AKL, **Add → Source** (or edit the existing filesystem source):
   - Scanner: **default / filesystem** (`script.akl.defaults`)
   - Path: `Z:\games\steam-installed`
   - Extensions: **`cmd`** (not `url`)
   - Platform: Windows / PC
   - Assets: `Z:\games\assets\source\steam`
   - Scan now (after re-running the sync script so `.cmd` files exist)
4. **Launcher** for that source:
   - Prefer **directly execute the file** once items are `.cmd`, **or**
   - Default app launcher: application `C:\Windows\System32\cmd.exe`, arguments `/c "$ROM$"`
   - Do **not** rely on `.url` + “open file itself” — AKL’s CreateProcess does not ShellExecute Internet Shortcuts, so launch appears to do nothing.
5. Open one title from the source. Steam should start the game.
6. Scrape the source: **SteamGridDB** (art) and/or **TheGamesDB** / Steam scraper (metadata). Existing art under `assets\source\steam` is reused.
7. After installing or uninstalling in Steam, either wait for the hourly task or run `Sync-SteamInstalled.ps1` / `Start-ScheduledTask`, then in AKL: context menu on the source → **Scan for new ROMs**.

## Day-to-day

| Action | What happens |
|---|---|
| Install a Steam game | Next sync writes a new `.cmd` → AKL rescan shows it |
| Uninstall | Sync deletes the `.cmd` → AKL rescan removes it |
| Rename not needed | Names come from Steam’s `name` field in the manifest |

## Troubleshooting

- **Scan/scrape works, launch does nothing**: you were on `.url` with “execute file itself”. Re-sync to `.cmd`, set source extension to `cmd`, rescan, keep direct-execute or `cmd.exe /c "$ROM$"`.
- **`Cannot find drive Z:` / empty Z: in PowerShell**: Explorer has `Z:` but this shell does not — almost always **UAC**. Mapped drives from a normal session are invisible to an elevated PowerShell (and the reverse). Use a **non-admin** PowerShell, or pass UNC:
  ```powershell
  .\Sync-SteamInstalled.ps1 -OutputDir '\\CORE\shared\games\steam-installed'
  ```
  The sync script will also auto-fall back to `\\CORE\shared\games\steam-installed` when it already sees that UNC Steam library and `Z:` is missing.
- **Empty output**: Steam not found → pass `-SteamRoot 'C:\Program Files (x86)\Steam'`. Or `libraryfolders.vdf` missing / no `appmanifest_*.acf` under `steamapps`.
- **Z: missing at logon**: task has a 2-minute delay; if the share mounts later, bump delay or run the task again after login. Prefer registering the task with UNC `-OutputDir` so it does not depend on `Z:`.
- **AKL still shows owned-but-not-installed**: that is the old Web API source. Use only the filesystem source pointed at `steam-installed`.
- **Tools appearing**: add AppIDs to `$SkipAppIds` or name patterns to `$SkipNamePatterns` in `Sync-SteamInstalled.ps1`.
