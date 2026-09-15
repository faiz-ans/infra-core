# Prepare the HTPC USB as BACKUP_DRIVE for Restic REST. Safe to re-run after
# a wipe (mkdir, firewall, Docker smoke test are idempotent).
#
#   powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1
#   powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1 -Wipe -ConfirmText ERASE
#   powershell -ExecutionPolicy Bypass -File bootstrap\periphery\htpc-backup-drive.ps1 -RestPassword '<from Komodo>'
#
# Run elevated on the HTPC console. -Wipe erases the volume; it is not the default.
# After a wipe, quit Docker Desktop fully and start it again so WSL2 rescans the letter.
# ASCII-only: Windows PowerShell 5.1 misreads UTF-8 en-dashes as smart quotes.
#Requires -Version 5.1
#Requires -RunAsAdministrator
param(
  [ValidatePattern('^[A-Za-z]$')]
  [string]$DriveLetter = 'D',
  [string]$Label = 'RESTIC',
  [switch]$Wipe,
  [string]$ConfirmText = '',
  [string]$RestUser = 'restic',
  [string]$RestPassword = '',
  [switch]$SkipUsbCheck,
  [switch]$SkipSizeCheck
)

$ErrorActionPreference = 'Stop'
$DriveLetter = $DriveLetter.ToUpperInvariant()
$root = $DriveLetter + ':'
$resticDir = Join-Path $root 'restic'
$htpasswd = Join-Path $root 'htpasswd'
$minBytes = [int64]3000000000000
$maxBytes = [int64]4800000000000

function Invoke-NativeDocker {
  param([string[]]$ArgList)
  $eap = $ErrorActionPreference
  # PS 5.1 turns native stderr into ErrorRecords. docker pull/run always
  # prints "Unable to find image locally" there; Stop would abort the pull.
  $ErrorActionPreference = 'Continue'
  try {
    $output = & docker @ArgList 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $eap
  }
  return [pscustomobject]@{ ExitCode = $code; Output = $output }
}

function Get-BackupDisk {
  $part = Get-Partition -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
  if (-not $part) {
    Write-Error ('{0} has no partition. Plug the USB in and assign {0} in Disk Management.' -f $root)
  }
  return Get-Disk -Number $part.DiskNumber
}

function Test-DockerBind {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'htpc-backup-drive: docker not on PATH; skip bind smoke test.'
    return
  }
  $probe = $root + '/restic'
  Write-Host ('htpc-backup-drive: docker bind smoke test ({0})...' -f $probe)
  $pull = Invoke-NativeDocker -ArgList @('pull', 'alpine:3.20')
  if ($pull.ExitCode -ne 0) {
    Write-Host ($pull.Output -join "`n")
    Write-Error 'docker pull alpine:3.20 failed. Is Docker Desktop running?'
  }
  $run = Invoke-NativeDocker -ArgList @('run', '--rm', '-v', ($probe + ':/probe:ro'), 'alpine:3.20', 'ls', '/probe')
  if ($run.ExitCode -ne 0) {
    Write-Host ($run.Output -join "`n")
    $wslPath = '/run/desktop/mnt/host/' + $DriveLetter.ToLowerInvariant()
    Write-Error (@(
        ('Docker Desktop cannot bind {0} (WSL2 looks under {1}).' -f $probe, $wslPath)
        'Quit Docker Desktop fully, start it again, then re-run this script without -Wipe.'
        'If it still fails, Windows is treating the USB as Removable (Docker only auto-shares Fixed letters). See bootstrap/first-run/restic.md.'
      ) -join "`n")
  }
  Write-Host ('htpc-backup-drive: Docker can read {0}.' -f $probe)
}

if ($DriveLetter -eq 'C') {
  Write-Error 'Refusing to touch C:.'
}

$disk = Get-BackupDisk
$sysDisk = (Get-Partition -DriveLetter C | Select-Object -First 1).DiskNumber
if ($disk.Number -eq $sysDisk) {
  Write-Error ('Refusing: {0} is on the Windows system disk (disk {1}).' -f $root, $disk.Number)
}

$bytes = [int64]$disk.Size
$tb = [math]::Round($bytes / 1e12, 2)
Write-Host ('htpc-backup-drive: disk {0} {1} BusType={2} {3} TB -> {4}' -f $disk.Number, $disk.FriendlyName, $disk.BusType, $tb, $root)

if (-not $SkipUsbCheck -and $disk.BusType -ne 'USB' -and $disk.BusType -ne 'External') {
  Write-Error ('BusType={0}, expected USB. Pass -SkipUsbCheck if this is the backup disk.' -f $disk.BusType)
}

if (-not $SkipSizeCheck -and ($bytes -lt $minBytes -or $bytes -gt $maxBytes)) {
  Write-Error ('Size {0} TB is outside the 4TB USB window (3.0-4.8 TB). Pass -SkipSizeCheck if this is the backup disk.' -f $tb)
}

$vol = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
if ($vol -and $vol.DriveType -eq 'Removable') {
  Write-Host 'htpc-backup-drive: warning: Windows DriveType=Removable. Docker Desktop often cannot bind those letters. Prefer a USB HDD enclosure that shows as Fixed.'
}

if ($Wipe) {
  if ($ConfirmText -ne 'ERASE') {
    Write-Error ('Refusing to wipe {0}. Re-run with -Wipe -ConfirmText ERASE (erases all data on disk {1}).' -f $root, $disk.Number)
  }
  Write-Host ('htpc-backup-drive: wiping disk {0} ({1} TB). All data on {2} will be gone.' -f $disk.Number, $tb, $root)
  Clear-Disk -Number $disk.Number -RemoveData -Confirm:$false
  Set-Disk -Number $disk.Number -IsOffline $false -IsReadOnly $false
  Initialize-Disk -Number $disk.Number -PartitionStyle GPT
  $null = New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter $DriveLetter
  Start-Sleep -Seconds 2
  $null = Format-Volume -DriveLetter $DriveLetter -FileSystem NTFS -NewFileSystemLabel $Label -Confirm:$false
  $disk = Get-BackupDisk
  Write-Host ('htpc-backup-drive: formatted {0} NTFS label {1}.' -f $root, $Label)
}

if (-not (Test-Path -LiteralPath $root)) {
  Write-Error ('{0} is not mounted. Assign the letter in Disk Management, then re-run without -Wipe.' -f $root)
}

New-Item -ItemType Directory -Force -Path $resticDir | Out-Null
Write-Host ('htpc-backup-drive: {0} ready.' -f $resticDir)

if ($RestPassword) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'docker is required to write htpasswd. Install Docker Desktop or omit -RestPassword and create the file later.'
  }
  $ht = Invoke-NativeDocker -ArgList @('run', '--rm', '--entrypoint', 'htpasswd', 'httpd:2', '-Bbn', $RestUser, $RestPassword)
  $line = ($ht.Output | Where-Object { $_ -match '^\S+:' } | Select-Object -Last 1)
  if ($ht.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($line)) {
    Write-Host ($ht.Output -join "`n")
    Write-Error 'htpasswd generation failed.'
  }
  Set-Content -LiteralPath $htpasswd -Value $line.TrimEnd() -Encoding ascii -NoNewline
  Add-Content -LiteralPath $htpasswd -Value '' -Encoding ascii
  Write-Host ('htpc-backup-drive: wrote {0} for user {1}.' -f $htpasswd, $RestUser)
} elseif (-not (Test-Path -LiteralPath $htpasswd)) {
  Write-Host ('htpc-backup-drive: no {0} yet. After Komodo RESTIC_REST_* exist, re-run with -RestUser / -RestPassword.' -f $htpasswd)
}

$ruleName = 'Restic REST'
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
  $null = New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
  Write-Host 'htpc-backup-drive: firewall allowed TCP 8000 (Private).'
}

if ($Wipe) {
  Write-Host ''
  Write-Host 'Quit Docker Desktop fully, start it again, then re-run this script without -Wipe (mkdir + bind smoke test).'
  Write-Host ('Komodo BACKUP_DRIVE = {0}  (no trailing slash; compose mounts {0}/restic and {0}/htpasswd).' -f $root)
  exit 0
}

Test-DockerBind

Write-Host ''
Write-Host ('Komodo BACKUP_DRIVE = {0}  (no trailing slash).' -f $root)
Write-Host 'Next: bootstrap/first-run/restic.md - secrets, htpasswd if still missing, Deploy restic-rest then restic.'
