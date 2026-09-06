# HTPC recovery after Docker Desktop hang / stale NFS / full C:.
# Prefer fixing root causes via bootstrap/periphery-docker-engine.ps1 + Core omv-nfs.sh.
# Usage:
#   powershell -ExecutionPolicy Bypass -File bootstrap\htpc-recover.ps1
param(
  [string]$NasIp = "192.168.1.110",
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Continue"

function Wait-Docker {
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $v = docker version --format "{{.Server.Version}}" 2>$null
      if ($v) {
        Write-Host "Docker engine: $v"
        return $true
      }
    } catch {}
    Start-Sleep -Seconds 2
  }
  Write-Host "ERROR: Docker engine not ready. Start Docker Desktop and re-run."
  return $false
}

Write-Host "=== 1. Quit Docker + WSL reset ==="
Get-Process "*Docker*" -ErrorAction SilentlyContinue | Stop-Process -Force
wsl --shutdown
Start-Sleep -Seconds 3

$crashDir = Join-Path $env:LOCALAPPDATA "Temp\wsl-crashes"
if (Test-Path $crashDir) {
  Remove-Item -Force "$crashDir\*" -ErrorAction SilentlyContinue
  Write-Host "Cleared wsl-crashes."
}

Write-Host "Start Docker Desktop now, then press Enter..."
$null = Read-Host
if (-not (Wait-Docker)) { exit 1 }

Write-Host "=== 2. Clear broken NFS volume state ==="
$clearCmd = 'for m in $(mount 2>/dev/null | awk ''/nfs|192.168.1./{print $3}''); do umount -lf "$m" 2>/dev/null; done; rm -rf /var/lib/docker/volumes/nas-nfs-shared /var/lib/docker/volumes/nfs-shared-test /var/lib/docker/volumes/nfs-s-test /var/lib/docker/volumes/nfs-u-test'
wsl -d docker-desktop sh -c $clearCmd 2>$null
docker volume rm -f nas-nfs-shared nfs-shared-test nfs-s-test nfs-u-test 2>$null
docker volume prune -f 2>$null

Write-Host "=== 3. Engine pools, log caps, disk cap ==="
if (-not $RepoRoot) {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  $parent = Split-Path -Parent $here
  if (Test-Path (Join-Path $parent "bootstrap\periphery-docker-engine.ps1")) {
    $RepoRoot = $parent
  } else {
    $RepoRoot = $here
  }
}
$enginePs1 = Join-Path $RepoRoot "bootstrap\periphery-docker-engine.ps1"
if (-not (Test-Path $enginePs1)) {
  $enginePs1 = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "periphery-docker-engine.ps1"
}
if (Test-Path $enginePs1) {
  powershell -ExecutionPolicy Bypass -File $enginePs1
  Write-Host "Quit Docker Desktop fully, start it, press Enter..."
  $null = Read-Host
  if (-not (Wait-Docker)) { exit 1 }
} else {
  Write-Host "WARN: periphery-docker-engine.ps1 not found."
}

Write-Host "=== 4. NFS soft smoke test ==="
docker volume create --name nfs-s-test --driver local --opt type=nfs --opt o="addr=${NasIp},nfsvers=4,rw,nolock,soft,timeo=50,retrans=2" --opt device=:/shared | Out-Host
$nfsOut = docker run --rm -v nfs-s-test:/shared alpine ls /shared/media /shared/photos 2>&1
Write-Host $nfsOut
if ($LASTEXITCODE -ne 0) {
  Write-Host "NFS :/shared failed. On Core: sudo HTPC_IP=<htpc> bash bootstrap/omv-nfs.sh"
  docker volume rm -f nfs-s-test 2>$null
  exit 1
}
docker volume rm -f nfs-s-test | Out-Null
Write-Host "SUCCESS: NFS shared OK. Recreate Periphery, Deploy stacks one at a time."
exit 0
