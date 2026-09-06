# Merge catalog Docker Engine settings into Docker Desktop + cap the WSL data disk.
# Layer 0 on the HTPC. Run after Docker Desktop is installed, before ResourceSync
# applies stacks-periphery.toml. Then restart Docker Desktop.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap/periphery-docker-engine.ps1
#   powershell -ExecutionPolicy Bypass -File bootstrap/periphery-docker-engine.ps1 -DiskSizeGiB 80
#
# Merges into %USERPROFILE%\.docker\daemon.json:
#   default-address-pools, log-driver, log-opts
# Sets %APPDATA%\Docker\settings-store.json DiskSizeMiB (WSL2 has no reliable GUI slider).
# Clears oversized WSL crash dumps under %LOCALAPPDATA%\Temp\wsl-crashes (can fill C:).
# Does not restart Docker. Does not write LAN IPs or site secrets.
param(
  [int]$DiskSizeGiB = 80
)

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $here
$fragment = Join-Path $repo "windows\docker-engine.json"
if (-not (Test-Path $fragment)) {
  $fragment = Join-Path $here "docker-engine.json"
}
if (-not (Test-Path $fragment)) {
  Write-Error "windows/docker-engine.json not found (clone the catalog, or copy that file next to this script)."
}

# --- daemon.json (address pools + log rotation) ---
$dockerDir = Join-Path $env:USERPROFILE ".docker"
$dest = Join-Path $dockerDir "daemon.json"
New-Item -ItemType Directory -Force -Path $dockerDir | Out-Null

$frag = Get-Content $fragment -Raw | ConvertFrom-Json
$pools = $frag.'default-address-pools'
if (-not $pools) {
  Write-Error "$fragment has no default-address-pools."
}

if (Test-Path $dest) {
  $raw = Get-Content $dest -Raw
  if ([string]::IsNullOrWhiteSpace($raw)) {
    $daemon = [pscustomobject]@{}
  } else {
    $daemon = $raw | ConvertFrom-Json
  }
} else {
  $daemon = [pscustomobject]@{}
}

$daemon | Add-Member -MemberType NoteProperty -Name "default-address-pools" -Value $pools -Force
if ($frag.'log-driver') {
  $daemon | Add-Member -MemberType NoteProperty -Name "log-driver" -Value $frag.'log-driver' -Force
}
if ($frag.'log-opts') {
  $daemon | Add-Member -MemberType NoteProperty -Name "log-opts" -Value $frag.'log-opts' -Force
}

$tmp = Join-Path $dockerDir "daemon.json.tmp"
$daemon | ConvertTo-Json -Depth 8 | Set-Content -Path $tmp -Encoding utf8
Move-Item -Force $tmp $dest
Write-Host "Wrote Engine settings to $dest (address pools + log rotation)."

# --- DiskSizeMiB (WSL2 data VHD cap) ---
$diskMiB = [int]($DiskSizeGiB * 1024)
$settingsDir = Join-Path $env:APPDATA "Docker"
$settings = Join-Path $settingsDir "settings-store.json"
New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
if (Test-Path $settings) {
  $rawSettings = Get-Content $settings -Raw
  if ([string]::IsNullOrWhiteSpace($rawSettings)) {
    $store = [pscustomobject]@{}
  } else {
    $store = $rawSettings | ConvertFrom-Json
  }
} else {
  $store = [pscustomobject]@{}
}
$store | Add-Member -NotePropertyName DiskSizeMiB -NotePropertyValue $diskMiB -Force
$settingsTmp = Join-Path $settingsDir "settings-store.json.tmp"
$store | ConvertTo-Json -Depth 30 | Set-Content -Path $settingsTmp -Encoding utf8
Move-Item -Force $settingsTmp $settings
Write-Host "Set DiskSizeMiB=$diskMiB (~${DiskSizeGiB} GiB) in $settings"

# --- WSL crash dumps (can be 100GB+ and fill C:) ---
$crashDir = Join-Path $env:LOCALAPPDATA "Temp\wsl-crashes"
if (Test-Path $crashDir) {
  $dumps = Get-ChildItem $crashDir -File -ErrorAction SilentlyContinue
  $bytes = ($dumps | Measure-Object -Property Length -Sum).Sum
  if ($bytes -gt 0) {
    Remove-Item -Force "$crashDir\*" -ErrorAction SilentlyContinue
    Write-Host ("Cleared wsl-crashes ({0:N1} GB)." -f ($bytes / 1GB))
  }
}

Write-Host ""
Write-Host "Quit Docker Desktop fully, then start it again."
Write-Host "New containers pick up log-opts; Redeploy existing stacks after restart if LogConfig is empty."
Write-Host "Then start Periphery (bootstrap/periphery.md)."
Write-Host "First HTPC bring-up: Deploy stacks one at a time (cold image pulls)."
