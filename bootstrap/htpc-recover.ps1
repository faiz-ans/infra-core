# HTPC recovery after Docker Desktop NFS hang / stale file handle.
# Run in PowerShell on the HTPC. Start Docker Desktop first; wait until it is idle.
# Usage:
#   powershell -ExecutionPolicy Bypass -File htpc-recover.ps1
#   powershell -ExecutionPolicy Bypass -File htpc-recover.ps1 -SmbUser faiz -SmbPassword 'YOUR_SMB_PASSWORD'
param(
  [string]$NasIp = "192.168.1.110",
  [string]$SmbUser = "",
  [string]$SmbPassword = "",
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
$clearCmd = 'for m in $(mount 2>/dev/null | awk ''/nfs|192.168.1./{print $3}''); do umount -lf "$m" 2>/dev/null; done; rm -rf /var/lib/docker/volumes/nas-nfs-shared /var/lib/docker/volumes/nfs-shared-test /var/lib/docker/volumes/smb-shared-test'
wsl -d docker-desktop sh -c $clearCmd 2>$null
docker volume rm -f nas-nfs-shared nfs-shared-test smb-shared-test 2>$null
docker volume prune -f 2>$null

Write-Host "=== 3. Engine address pools ==="
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

Write-Host "=== 4. NFS v3 smoke test ==="
docker volume create --name nfs-shared-test --driver local --opt type=nfs --opt o="addr=${NasIp},nfsvers=3,rw,nolock,soft,timeo=50,retrans=2" --opt device=:/export/shared | Out-Host

$nfsOut = docker run --rm -v nfs-shared-test:/shared alpine ls /shared/media 2>&1
Write-Host $nfsOut
if ($LASTEXITCODE -eq 0) {
  Write-Host "SUCCESS: NFS works. Remove test volume and continue with Komodo deploys."
  docker volume rm -f nfs-shared-test | Out-Null
  Write-Host ""
  Write-Host "Next (Komodo), one stack at a time - wait for Up:"
  Write-Host "  glances-periphery -> dockerproxy -> jellyfin -> arr -> qbittorrent"
  Write-Host "  -> homeassistant -> seerr -> pihole-periphery -> collabora -> frigate"
  Write-Host "  -> immich -> then the rest. Skip restic-rest."
  Write-Host ""
  Write-Host "Recreate Periphery if needed:"
  Write-Host "  docker compose --env-file periphery.env -f periphery.compose.yaml up -d"
  exit 0
}

Write-Host "NFS failed. Cleaning again..."
docker volume rm -f nfs-shared-test 2>$null
Get-Process "*Docker*" -ErrorAction SilentlyContinue | Stop-Process -Force
wsl --shutdown
Start-Sleep -Seconds 3
Write-Host "Start Docker Desktop, press Enter..."
$null = Read-Host
if (-not (Wait-Docker)) { exit 1 }

if (-not $SmbUser -or -not $SmbPassword) {
  Write-Host ""
  Write-Host "NFS is broken on this Docker Desktop. Re-run with SMB credentials (same as Explorer):"
  Write-Host ""
  Write-Host "  powershell -ExecutionPolicy Bypass -File htpc-recover.ps1 -SmbUser faiz -SmbPassword 'YOUR_PASSWORD'"
  Write-Host ""
  exit 2
}

Write-Host "=== 5. SMB/CIFS smoke test (bypass NFS) ==="
$o = "username=${SmbUser},password=${SmbPassword},vers=3.0,noperm,iocharset=utf8"
docker volume create --name smb-shared-test --driver local --opt type=cifs --opt o=$o --opt device="//${NasIp}/shared" | Out-Host

$smbOut = docker run --rm -v smb-shared-test:/shared alpine ls /shared/media 2>&1
Write-Host $smbOut
if ($LASTEXITCODE -eq 0) {
  Write-Host "SUCCESS: SMB works from Docker. NFS stacks will still hang until compose is switched to CIFS."
  Write-Host "Tell the agent: SMB smoke test OK - update periphery compose to CIFS."
  docker volume rm -f smb-shared-test | Out-Null
  exit 0
}

Write-Host "ERROR: Both NFS and SMB failed from Docker. Check OMV SMB share shared and credentials."
exit 3
