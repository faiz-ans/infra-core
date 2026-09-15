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
  [switch]$SkipSizeCheck,
  [int]$DiskNumber = -1
)

$ErrorActionPreference = 'Stop'
$DriveLetter = $DriveLetter.ToUpperInvariant()
# String concat only. Join-Path D: throws "Cannot find drive" when the letter
# is gone (which is the state after Clear-Disk).
$root = $DriveLetter + ':'
$resticDir = $root + '\restic'
$htpasswd = $root + '\htpasswd'
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

function Get-BackupExtras {
  if (-not (Get-PSDrive -Name $DriveLetter -ErrorAction SilentlyContinue)) {
    return @()
  }
  $keep = @('restic', 'htpasswd')
  return @(Get-ChildItem -LiteralPath $root -Force | Where-Object { $keep -notcontains $_.Name })
}

function Get-SystemDiskNumber {
  return (Get-Partition -DriveLetter C | Select-Object -First 1).DiskNumber
}

function Test-BackupDiskCandidate {
  param($Candidate, $SystemDisk)
  if ($Candidate.Number -eq $SystemDisk) { return $false }
  if (-not $SkipUsbCheck -and $Candidate.BusType -ne 'USB' -and $Candidate.BusType -ne 'External') { return $false }
  if (-not $SkipSizeCheck -and ($Candidate.Size -lt $minBytes -or $Candidate.Size -gt $maxBytes)) { return $false }
  return $true
}

function Get-BackupDisk {
  $sysDisk = Get-SystemDiskNumber
  if ($DiskNumber -ge 0) {
    $d = Get-Disk -Number $DiskNumber
    if (-not (Test-BackupDiskCandidate -Candidate $d -SystemDisk $sysDisk)) {
      throw ('Disk {0} ({1} {2} {3}) failed USB/size checks. Pass -SkipUsbCheck/-SkipSizeCheck if it is the backup disk.' -f $d.Number, $d.FriendlyName, $d.BusType, $d.Size)
    }
    return $d
  }

  $part = Get-Partition -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
  if ($part) {
    return Get-Disk -Number $part.DiskNumber
  }

  # After a failed wipe, Clear-Disk has already dropped the letter. Prefer the
  # matching USB that is still Raw.
  $cands = @(Get-Disk | Where-Object { Test-BackupDiskCandidate -Candidate $_ -SystemDisk $sysDisk })
  if ($cands.Count -eq 0) {
    throw ('{0} is missing and no USB disk in the 4TB window was found. Plug the drive in, or pass -DiskNumber.' -f $root)
  }
  if ($cands.Count -eq 1) {
    Write-Host ('htpc-backup-drive: {0} is missing; using disk {1} {2} ({3}).' -f $root, $cands[0].Number, $cands[0].FriendlyName, $cands[0].PartitionStyle)
    return $cands[0]
  }
  $raw = @($cands | Where-Object { $_.PartitionStyle -eq 'Raw' })
  if ($raw.Count -eq 1) {
    Write-Host ('htpc-backup-drive: {0} is missing; using raw disk {1} {2}.' -f $root, $raw[0].Number, $raw[0].FriendlyName)
    return $raw[0]
  }
  $list = ($cands | ForEach-Object { '{0}:{1}:{2}' -f $_.Number, $_.FriendlyName, $_.PartitionStyle }) -join ', '
  throw ('{0} is missing and multiple USB disks match ({1}). Pass -DiskNumber.' -f $root, $list)
}

function Set-BackupDiskOnline {
  param($Number)
  # -IsOffline and -IsReadOnly are different parameter sets on Windows PS 5.1.
  Set-Disk -Number $Number -IsOffline $false
  Set-Disk -Number $Number -IsReadOnly $false
}

function Wait-BackupLetter {
  param([int]$Seconds = 15)
  for ($i = 0; $i -lt $Seconds; $i++) {
    Update-HostStorageCache | Out-Null
    if (Get-PSDrive -Name $DriveLetter -PSProvider FileSystem -ErrorAction SilentlyContinue) {
      return
    }
    Start-Sleep -Seconds 1
  }
  throw ('Windows did not map {0} after format. Check Disk Management, or pass -DiskNumber.' -f $root)
}

function Initialize-BackupVolume {
  param($Number, [string]$Letter, [string]$VolLabel)
  # Storage cmdlets often leave USB GPT volumes as Explorer
  # "D:\ is not accessible. The parameter is incorrect." diskpart does not.
  Set-BackupDiskOnline -Number $Number
  $dpFile = $env:TEMP + '\htpc-backup-diskpart.txt'
  $script = @(
    'select disk ' + $Number
    'online disk'
    'attributes disk clear readonly'
    'clean'
    'convert gpt'
    'create partition primary'
    'format fs=ntfs quick label=' + $VolLabel
    'assign letter=' + $Letter
  )
  Set-Content -LiteralPath $dpFile -Value $script -Encoding Ascii
  Write-Host ('htpc-backup-drive: diskpart selecting disk {0} (clean / GPT / NTFS / {1}).' -f $Number, $Letter)
  $dp = & diskpart.exe /s $dpFile
  Write-Host ($dp -join "`n")
  $joined = $dp -join "`n"
  if ($joined -match 'The disk you specified is not valid' -or $joined -match 'Access is denied') {
    throw 'diskpart failed. Full output is above.'
  }
  Wait-BackupLetter
  $item = Get-Item -LiteralPath ($Letter + ':\') -ErrorAction SilentlyContinue
  if (-not $item) {
    throw ('{0}\ exists as a letter but Explorer cannot open it. Replug the USB, then re-run -Wipe.' -f $Letter)
  }
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
    throw 'docker pull alpine:3.20 failed. Is Docker Desktop running?'
  }
  $run = Invoke-NativeDocker -ArgList @('run', '--rm', '-v', ($probe + ':/probe:ro'), 'alpine:3.20', 'ls', '/probe')
  if ($run.ExitCode -ne 0) {
    Write-Host ($run.Output -join "`n")
    $wslPath = '/run/desktop/mnt/host/' + $DriveLetter.ToLowerInvariant()
    throw (@(
        ('Docker Desktop cannot bind {0} (WSL2 looks under {1}).' -f $probe, $wslPath)
        'Quit Docker Desktop fully, start it again, then re-run this script without -Wipe.'
        'If it still fails, Windows is treating the USB as Removable (Docker only auto-shares Fixed letters). See bootstrap/first-run/restic.md.'
      ) -join "`n")
  }
  Write-Host ('htpc-backup-drive: Docker can read {0}.' -f $probe)
}

if ($DriveLetter -eq 'C') {
  throw 'Refusing to touch C:.'
}

$disk = Get-BackupDisk
$sysDisk = Get-SystemDiskNumber
if ($disk.Number -eq $sysDisk) {
  throw ('Refusing: {0} is on the Windows system disk (disk {1}).' -f $root, $disk.Number)
}

$bytes = [int64]$disk.Size
$tb = [math]::Round($bytes / 1e12, 2)
Write-Host ('htpc-backup-drive: disk {0} {1} BusType={2} {3} TB -> {4}' -f $disk.Number, $disk.FriendlyName, $disk.BusType, $tb, $root)

if (-not $SkipUsbCheck -and $disk.BusType -ne 'USB' -and $disk.BusType -ne 'External') {
  throw ('BusType={0}, expected USB. Pass -SkipUsbCheck if this is the backup disk.' -f $disk.BusType)
}

if (-not $SkipSizeCheck -and ($bytes -lt $minBytes -or $bytes -gt $maxBytes)) {
  throw ('Size {0} TB is outside the 4TB USB window (3.0-4.8 TB). Pass -SkipSizeCheck if this is the backup disk.' -f $tb)
}

$vol = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
if ($vol -and $vol.DriveType -eq 'Removable') {
  Write-Host 'htpc-backup-drive: warning: Windows DriveType=Removable. Docker Desktop often cannot bind those letters. Prefer a USB HDD enclosure that shows as Fixed.'
}

if (-not $Wipe -and $disk.PartitionStyle -eq 'Raw') {
  throw ('Disk {0} is Raw (wipe stopped before a volume was created). Re-run with -Wipe -ConfirmText ERASE to format {1}.' -f $disk.Number, $root)
}

if ($Wipe) {
  if ($ConfirmText -ne 'ERASE') {
    throw ('Refusing to wipe {0}. Re-run with -Wipe -ConfirmText ERASE (erases all data on disk {1}).' -f $root, $disk.Number)
  }
  Write-Host ('htpc-backup-drive: wiping disk {0} ({1} TB). All data on {2} will be gone.' -f $disk.Number, $tb, $root)
  Write-Host 'htpc-backup-drive: close Explorer windows on that letter. If Docker already bound it, quit Docker Desktop first.'
  if ($disk.PartitionStyle -ne 'Raw') {
    Clear-Disk -Number $disk.Number -RemoveData -Confirm:$false
  } else {
    Write-Host 'htpc-backup-drive: disk is already Raw (previous wipe stopped after Clear-Disk). Creating the volume.'
  }
  Initialize-BackupVolume -Number $disk.Number -Letter $DriveLetter -VolLabel $Label
  $disk = Get-BackupDisk
  Write-Host ('htpc-backup-drive: formatted {0} NTFS label {1}.' -f $root, $Label)
}

if (-not (Get-PSDrive -Name $DriveLetter -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
  throw ('{0} is not mounted. Re-run with -Wipe -ConfirmText ERASE, or assign the letter in Disk Management.' -f $root)
}

New-Item -ItemType Directory -Force -Path $resticDir | Out-Null
Write-Host ('htpc-backup-drive: {0} ready.' -f $resticDir)

if (-not $Wipe) {
  $extras = Get-BackupExtras
  if ($extras.Count -gt 0) {
    Write-Host ('htpc-backup-drive: {0} still has {1} other item(s) besides restic/htpasswd. This run does not erase them.' -f $root, $extras.Count)
    Write-Host 'htpc-backup-drive: to GPT-format the USB, quit Docker Desktop if it bound D:, then:'
    Write-Host '  powershell -ExecutionPolicy Bypass -File htpc-backup-drive.ps1 -Wipe -ConfirmText ERASE'
  }
}

if ($RestPassword) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker is required to write htpasswd. Install Docker Desktop or omit -RestPassword and create the file later.'
  }
  $ht = Invoke-NativeDocker -ArgList @('run', '--rm', '--entrypoint', 'htpasswd', 'httpd:2', '-Bbn', $RestUser, $RestPassword)
  $line = ($ht.Output | Where-Object { $_ -match '^\S+:' } | Select-Object -Last 1)
  if ($ht.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($line)) {
    Write-Host ($ht.Output -join "`n")
    throw 'htpasswd generation failed.'
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
