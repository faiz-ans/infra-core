# Merge catalog Docker Engine address pools into Docker Desktop's daemon.json.
# Layer 0 on the HTPC. Run after Docker Desktop is installed, before ResourceSync
# applies stacks-periphery.toml. Then restart Docker Desktop.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap/periphery-docker-engine.ps1
#
# Does not restart Docker. Does not write LAN IPs or site secrets.

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

$pools = (Get-Content $fragment -Raw | ConvertFrom-Json).'default-address-pools'
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

$dir = Split-Path $dest
$tmp = Join-Path $dir "daemon.json.tmp"
$daemon | ConvertTo-Json -Depth 8 | Set-Content -Path $tmp -Encoding utf8
Move-Item -Force $tmp $dest

Write-Host "Wrote default-address-pools to $dest"
Write-Host "Restart Docker Desktop, then start Periphery (bootstrap/periphery.md)."
