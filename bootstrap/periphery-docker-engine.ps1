# Merge catalog Docker Engine settings into Docker Desktop's daemon.json.
# Layer 0 on the HTPC. Run after Docker Desktop is installed, before ResourceSync
# applies stacks-periphery.toml. Then restart Docker Desktop.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap/periphery-docker-engine.ps1
#
# Merges: default-address-pools, log-driver, log-opts (caps container logs so the
# WSL VHD cannot fill C: unboundedly). Leaves other Engine keys alone.
# Does not restart Docker. Does not write LAN IPs or site secrets.
# Also set Docker Desktop → Settings → Resources → Disk image size (e.g. 64-80 GB).

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

$dir = Split-Path $dest
$tmp = Join-Path $dir "daemon.json.tmp"
$daemon | ConvertTo-Json -Depth 8 | Set-Content -Path $tmp -Encoding utf8
Move-Item -Force $tmp $dest

Write-Host "Wrote Engine settings to $dest (address pools + log rotation)."
Write-Host "In Docker Desktop: Settings -> Resources -> set Disk image size (e.g. 64-80 GB)."
Write-Host "Restart Docker Desktop, then start Periphery (bootstrap/periphery.md)."
