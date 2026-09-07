#Requires -Version 5.1
<#
.SYNOPSIS
  Build a folder of named Steam .url shortcuts for games installed on this PC.

.DESCRIPTION
  Reads Steam libraryfolders.vdf, finds appmanifest_*.acf in each library's
  steamapps folder, and writes "<Game Name>.cmd" scripts that run
  steam://rungameid/<appid>. Removes shortcuts for games that are no longer
  installed. Point AKL's default file scanner at the output folder
  (extension: cmd). .cmd is used instead of .url because Kodi/AKL launchers
  typically CreateProcess the file; .url only works via Explorer ShellExecute.

.PARAMETER OutputDir
  Folder for the .cmd shortcuts (AKL source path).
  Default: Z:\games\steam-installed when Z: exists; otherwise
  \\<nas>\shared\games\steam-installed derived from Steam's library UNC.

.PARAMETER SteamRoot
  Steam install root if auto-detect fails. Default: registry / Program Files.

.PARAMETER WhatIf
  Show what would change without writing files.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$OutputDir = 'Z:\games\steam-installed',
    [string]$SteamRoot
)

$ErrorActionPreference = 'Stop'

# Known non-game / tool AppIDs and name fragments to skip.
$SkipAppIds = [System.Collections.Generic.HashSet[string]]::new([string[]]@(
    '228980'   # Steamworks Common Redistributables
    '1070560'  # Steam Linux Runtime
    '1391110'  # Steam Linux Runtime - Soldier
    '1628350'  # Steam Linux Runtime - Sniper
    '1493710'  # Proton Experimental
    '1887720'  # Proton 8.0
    '2805730'  # Proton 9.0
    '961940'   # Proton 3.7 Beta
    '858280'   # Proton 3.7
    '930400'   # Proton 3.16 Beta
    '1113280'  # Proton 4.11
    '1245040'  # Proton 5.0
    '1420170'  # Proton 5.13
    '1580130'  # Proton 6.3
    '2230260'  # SteamOS
))

$SkipNamePatterns = @(
    '^Steamworks Common Redistributables$'
    '^Steam Linux Runtime'
    '^Proton '
    '^SteamVR'
    '^Steam Controller'
    '^Steam Input'
)

function Get-SteamRoot {
    param([string]$Override)
    if ($Override -and (Test-Path -LiteralPath $Override)) {
        return (Resolve-Path -LiteralPath $Override).Path
    }
    $regPaths = @(
        'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'
        'HKLM:\SOFTWARE\Valve\Steam'
        'HKCU:\SOFTWARE\Valve\Steam'
    )
    foreach ($rp in $regPaths) {
        try {
            $install = (Get-ItemProperty -Path $rp -ErrorAction Stop).InstallPath
            if ($install -and (Test-Path -LiteralPath $install)) {
                return $install
            }
        } catch { }
    }
    $fallback = "${env:ProgramFiles(x86)}\Steam"
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    throw 'Steam install not found. Pass -SteamRoot explicitly.'
}

function Get-VdfStringValue {
    param(
        [string]$Text,
        [string]$Key
    )
    # Matches: "key"  "value"  (tabs/spaces between)
    $pattern = '"' + [regex]::Escape($Key) + '"\s+"([^"]*)"'
    $m = [regex]::Match($Text, $pattern)
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

function Get-SteamLibraryPaths {
    param([string]$Root)
    $vdf = Join-Path $Root 'steamapps\libraryfolders.vdf'
    $paths = [System.Collections.Generic.List[string]]::new()
    $paths.Add($Root) | Out-Null

    if (-not (Test-Path -LiteralPath $vdf)) {
        Write-Warning "libraryfolders.vdf missing at $vdf; only using Steam root."
        return $paths
    }

    $content = Get-Content -LiteralPath $vdf -Raw -Encoding UTF8
    # Each library entry has "path" "C:\\..."
    foreach ($m in [regex]::Matches($content, '"path"\s+"([^"]+)"')) {
        $p = $m.Groups[1].Value -replace '\\\\', '\'
        if ($p -and (Test-Path -LiteralPath $p) -and -not ($paths -contains $p)) {
            $paths.Add($p) | Out-Null
        }
    }
    return $paths
}

function Test-SkipGame {
    param(
        [string]$AppId,
        [string]$Name
    )
    if ($SkipAppIds.Contains($AppId)) { return $true }
    foreach ($pat in $SkipNamePatterns) {
        if ($Name -match $pat) { return $true }
    }
    return $false
}

function Get-SafeFileName {
    param([string]$Name)
    $invalid = [IO.Path]::GetInvalidFileNameChars()
    $sb = [System.Text.StringBuilder]::new($Name.Length)
    foreach ($ch in $Name.ToCharArray()) {
        if ($invalid -contains $ch) {
            [void]$sb.Append('_')
        } else {
            [void]$sb.Append($ch)
        }
    }
    $safe = $sb.ToString().Trim().TrimEnd('.')
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = 'Unknown Game' }
    # Avoid reserved device names
    if ($safe -match '^(CON|PRN|AUX|NUL|COM\d|LPT\d)$') { $safe = "_$safe" }
    return $safe
}

function Get-InstalledSteamGames {
    param([string[]]$LibraryRoots)

    $games = @{}  # appid -> @{ AppId; Name; Library }

    foreach ($lib in $LibraryRoots) {
        $steamapps = Join-Path $lib 'steamapps'
        if (-not (Test-Path -LiteralPath $steamapps)) { continue }

        Get-ChildItem -LiteralPath $steamapps -Filter 'appmanifest_*.acf' -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                $text = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
                $appId = Get-VdfStringValue -Text $text -Key 'appid'
                $name = Get-VdfStringValue -Text $text -Key 'name'
                if (-not $appId) {
                    if ($_.BaseName -match '^appmanifest_(\d+)$') { $appId = $Matches[1] }
                }
                if (-not $appId) { return }
                if (-not $name) { $name = "Steam App $appId" }
                if (Test-SkipGame -AppId $appId -Name $name) {
                    Write-Verbose "Skip $appId ($name)"
                    return
                }
                $games[$appId] = @{
                    AppId   = $appId
                    Name    = $name
                    Library = $lib
                }
            }
    }
    return $games
}

function Write-SteamCmd {
    param(
        [string]$Path,
        [string]$AppId
    )
    # cmd + start uses ShellExecute so steam:// is honored (CreateProcess alone cannot).
    $body = @"
@echo off
start "" "steam://rungameid/$AppId"
"@
    [IO.File]::WriteAllText($Path, $body, [Text.UTF8Encoding]::new($false))
}

function Test-PathRootAvailable {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    # UNC: \\server\share\...
    if ($Path -match '^\\\\[^\\]+\\[^\\]+') {
        $shareRoot = ($Path -replace '^(\\\\[^\\]+\\[^\\]+).*', '$1')
        return (Test-Path -LiteralPath $shareRoot)
    }
    # Drive letter: Z:\...
    if ($Path -match '^([A-Za-z]):') {
        $drive = $Matches[1] + ':'
        return [bool](Get-PSDrive -Name $Matches[1] -ErrorAction SilentlyContinue) -or
            (Test-Path -LiteralPath $drive)
    }
    return (Test-Path -LiteralPath $Path)
}

function Resolve-OutputDir {
    param(
        [string]$Requested,
        [string[]]$LibraryRoots
    )
    if (Test-PathRootAvailable -Path $Requested) {
        return $Requested
    }

    # Z: (or other letter) missing in this session — common when the drive was
    # mapped in Explorer as a normal user and PowerShell is elevated (or vice versa).
    # Prefer a UNC sibling of the NAS Steam library: ...\games\steam → ...\games\steam-installed
    foreach ($lib in $LibraryRoots) {
        if ($lib -match '^(\\\\.+?)[\\/]+games[\\/]+steam(?:[\\/]+)?$') {
            $candidate = Join-Path $Matches[1] 'games\steam-installed'
            if (Test-PathRootAvailable -Path (Split-Path -Parent $candidate)) {
                Write-Warning "Drive/path unavailable for '$Requested'. Using UNC: $candidate"
                return $candidate
            }
        }
        # Also accept ...\games\steam with mixed separators already normalized
        if ($lib -like '*\games\steam' -or $lib -like '*/games/steam') {
            $parent = Split-Path -Parent $lib
            $candidate = Join-Path $parent 'steam-installed'
            if (Test-PathRootAvailable -Path $parent) {
                Write-Warning "Drive/path unavailable for '$Requested'. Using UNC: $candidate"
                return $candidate
            }
        }
    }

    throw @"
Cannot reach output path '$Requested'.
Steam libraries are visible (often as UNC), but this PowerShell session has no Z: drive.

Fix one of:
  1. Run a non-elevated PowerShell (same integrity level as Explorer's Z: mapping), or
  2. Pass UNC explicitly, e.g.:
       .\Sync-SteamInstalled.ps1 -OutputDir '\\CORE\shared\games\steam-installed'
"@
}

# --- main ---
$steam = Get-SteamRoot -Override $SteamRoot
Write-Host "Steam root: $steam"

$libs = @(Get-SteamLibraryPaths -Root $steam)
Write-Host "Libraries ($($libs.Count)):"
$libs | ForEach-Object { Write-Host "  $_" }

$installed = Get-InstalledSteamGames -LibraryRoots $libs
Write-Host "Installed games (after skips): $($installed.Count)"

$OutputDir = Resolve-OutputDir -Requested $OutputDir -LibraryRoots $libs
Write-Host "Output: $OutputDir"

if (-not (Test-Path -LiteralPath $OutputDir)) {
    if ($PSCmdlet.ShouldProcess($OutputDir, 'Create output directory')) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
}

# Desired map: safe filename -> appid (detect name collisions)
$desired = @{}  # full path -> appid
$nameCount = @{}
foreach ($g in $installed.Values) {
    $base = Get-SafeFileName -Name $g.Name
    if (-not $nameCount.ContainsKey($base)) { $nameCount[$base] = 0 }
    $nameCount[$base]++
    if ($nameCount[$base] -gt 1) {
        $base = "$base ($($g.AppId))"
    }
    $path = Join-Path $OutputDir ($base + '.cmd')
    # If two different names sanitized to same file before count bump, force appid suffix
    if ($desired.ContainsKey($path) -and $desired[$path] -ne $g.AppId) {
        $path = Join-Path $OutputDir ("$base ($($g.AppId)).cmd")
    }
    $desired[$path] = $g.AppId
}

$written = 0
foreach ($path in $desired.Keys) {
    $appId = $desired[$path]
    $needWrite = $true
    if (Test-Path -LiteralPath $path) {
        $existing = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
        if ($existing -match [regex]::Escape("steam://rungameid/$appId")) {
            $needWrite = $false
        }
    }
    if ($needWrite) {
        if ($PSCmdlet.ShouldProcess($path, "Write steam://rungameid/$appId")) {
            Write-SteamCmd -Path $path -AppId $appId
            $written++
        }
    }
}

# Remove stale .cmd (and leftover .url from older syncs) not in desired set
$removed = 0
$stale = @(
    Get-ChildItem -LiteralPath $OutputDir -Filter '*.cmd' -File -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $OutputDir -Filter '*.url' -File -ErrorAction SilentlyContinue
)
foreach ($file in $stale) {
    $keep = $false
    if ($file.Extension -eq '.cmd') {
        foreach ($k in $desired.Keys) {
            if ([string]::Equals($k, $file.FullName, [StringComparison]::OrdinalIgnoreCase)) {
                $keep = $true
                break
            }
        }
    }
    if (-not $keep) {
        if ($PSCmdlet.ShouldProcess($file.FullName, 'Remove stale shortcut')) {
            Remove-Item -LiteralPath $file.FullName -Force
            $removed++
        }
    }
}

Write-Host "Done. Wrote/updated: $written  Removed: $removed  Output: $OutputDir"
