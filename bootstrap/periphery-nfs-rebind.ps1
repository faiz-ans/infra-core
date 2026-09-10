# Recreate Docker NFS volumes whose baked addr= does not match Core's LAN IP.
# Compose interpolates NAS_LAN_IP at volume *create*; changing the Komodo var
# does not update existing volumes. Same DHCP reservation (NIC swap only) is a
# no-op. Local *-config volumes are left alone.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap\periphery-nfs-rebind.ps1 -NasIp 192.168.1.110
#
# Stop NFS stacks first (or pass -Force to stop containers using those volumes).
# Then Komodo → each NFS stack → Redeploy.
param(
  [Parameter(Mandatory = $true)]
  [string]$NasIp,
  [switch]$Force
)

$ErrorActionPreference = "Stop"

if ($NasIp -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
  Write-Error "NasIp must be an IPv4 address (Komodo NAS_LAN_IP)."
}

function Wait-Docker {
  for ($i = 0; $i -lt 30; $i++) {
    try {
      $v = docker version --format "{{.Server.Version}}" 2>$null
      if ($v) { return $true }
    } catch {}
    Start-Sleep -Seconds 2
  }
  Write-Error "Docker engine not ready."
}

Wait-Docker | Out-Null

$removed = @()
$ok = @()
$names = docker volume ls -q
foreach ($name in $names) {
  $insp = docker volume inspect $name | ConvertFrom-Json
  $opts = $insp[0].Options
  if (-not $opts) { continue }
  $o = [string]$opts.o
  $type = [string]$opts.type
  if ($type -ne "nfs" -and $o -notmatch "addr=") { continue }
  if ($o -match [regex]::Escape("addr=$NasIp")) {
    $ok += $name
    continue
  }
  if ($Force) {
    docker ps -aq --filter "volume=$name" | ForEach-Object { docker stop $_ 2>$null | Out-Null }
  }
  Write-Host "Removing stale NFS volume $name"
  Write-Host "  $o"
  docker volume rm -f $name
  $removed += $name
}

if ($ok.Count -gt 0) {
  Write-Host "Already on $NasIp : $($ok -join ', ')"
}
if ($removed.Count -eq 0) {
  Write-Host "No NFS volumes needed rebind."
} else {
  Write-Host "Removed: $($removed -join ', ')"
  Write-Host "Komodo → Redeploy each NFS stack (jellyfin, arr, qbittorrent, immich, frigate)."
}
exit 0
