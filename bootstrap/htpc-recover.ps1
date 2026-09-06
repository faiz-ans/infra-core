# HTPC recovery after Docker Desktop hang / stale NFS handle.
# Run in PowerShell on the HTPC. Start Docker Desktop first; wait until it is idle.
# Usage:
#   powershell -ExecutionPolicy Bypass -File htpc-recover.ps1
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
Write-Host "Start Docker Desktop now, then press Enter..."
$null = Read-Host

if (-not (Wait-Docker)) { exit 1 }

Write-Host "=== 2. Clear broken NFS volume state ==="
$clearCmd = 'for m in $(mount 2>/dev/null | awk ''/nfs|192.168.1./{print $3}''); do umount -lf "$m" 2>/dev/null; done; rm -rf /var/lib/docker/volumes/nas-nfs-shared /var/lib/docker/volumes/nfs-shared-test'
wsl -d docker-desktop sh -c $clearCmd 2>$null
docker volume rm -f nas-nfs-shared nfs-shared-test 2>$null
docker volume prune -f 2>$null

Write-Host "=== 3. Engine address pools + log rotation ==="
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
  $enginePs1 = Join-Path $here "periphery-docker-engine.ps1"
}
if (Test-Path $enginePs1) {
  powershell -ExecutionPolicy Bypass -File $enginePs1
  Write-Host "If the script asked to restart Desktop: Quit Docker, start it, press Enter..."
  $null = Read-Host
  if (-not (Wait-Docker)) { exit 1 }
} else {
  Write-Host "WARN: periphery-docker-engine.ps1 not found - skip pools."
}

Write-Host "=== 4. NFS smoke test ==="
docker volume create --name nfs-shared-test --driver local --opt type=nfs --opt o="addr=${NasIp},nfsvers=4,rw,nolock,soft,timeo=50,retrans=2" --opt device=:/shared | Out-Host

$nfsOut = docker run --rm -v nfs-shared-test:/shared alpine ls /shared/media 2>&1
Write-Host $nfsOut
if ($LASTEXITCODE -eq 0) {
  Write-Host "SUCCESS: NFS works."
  docker volume rm -f nfs-shared-test | Out-Null
  Write-Host "Recreate Periphery, then Deploy stacks (compose.nfs.yaml) one at a time if cold cache."
  exit 0
}

Write-Host "NFS failed. Cap Desktop disk image size, free C:, re-run periphery-docker-engine.ps1, retry."
docker volume rm -f nfs-shared-test 2>$null
exit 1
