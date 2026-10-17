# Register the Surface disk tasks: D: on/off, SMART self-tests, and one
# Scrutiny collect. Run once from an elevated PowerShell on Surface, while
# D: is online. GET/SET does not run this.
#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Install backup-disk power, SMART self-tests, and the Scrutiny collector.

.PARAMETER ApiEndpoint
  Scrutiny hub on Core. Not HTTPS.

.PARAMETER HostId
  Label in the Scrutiny UI for this machine's disks.
#>
param(
    [string]$ApiEndpoint = 'http://192.168.1.110:8087',

    [string]$HostId = 'surface'
)

$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'backup-disk.ps1'
$vbsSrc = Join-Path $PSScriptRoot 'backup-disk.vbs'
$invokeSrc = Join-Path $PSScriptRoot 'Invoke-ScrutinyCollector.ps1'
if (-not (Test-Path -LiteralPath $invokeSrc)) {
    $invokeSrc = Join-Path (Split-Path -Parent $PSScriptRoot) 'scrutiny-collector\Invoke-ScrutinyCollector.ps1'
}
if (-not (Test-Path -LiteralPath $src)) { throw "missing $src" }
if (-not (Test-Path -LiteralPath $vbsSrc)) { throw "missing $vbsSrc" }
if (-not (Test-Path -LiteralPath $invokeSrc)) { throw "missing $invokeSrc" }

$destDir = 'C:\ProgramData\backup-disk'
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$dest = Join-Path $destDir 'backup-disk.ps1'
$vbs = Join-Path $destDir 'backup-disk.vbs'
$invoke = Join-Path $destDir 'Invoke-ScrutinyCollector.ps1'
Copy-Item -LiteralPath $src -Destination $dest -Force
Copy-Item -LiteralPath $vbsSrc -Destination $vbs -Force
Copy-Item -LiteralPath $invokeSrc -Destination $invoke -Force

& $dest -Action Save

$smartctl = 'C:\Program Files\smartmontools\bin\smartctl.exe'
if (-not (Test-Path -LiteralPath $smartctl)) {
    throw "smartctl not found at $smartctl. Install smartmontools.smartmontools (winget / windows/packages.json)."
}

$exeName = 'scrutiny-collector-metrics-windows-amd64.exe'
$collector = Join-Path $destDir $exeName
if (-not (Test-Path -LiteralPath $collector)) {
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/AnalogJ/scrutiny/releases/latest' -Headers @{
        'User-Agent' = 'infra-core-scrutiny-collector'
    }
    $asset = $release.assets | Where-Object { $_.name -eq $exeName } | Select-Object -First 1
    if (-not $asset) {
        throw "GitHub release has no $exeName asset."
    }
    Write-Output ("Downloading " + $asset.browser_download_url)
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $collector -UseBasicParsing
}

$ApiEndpoint = $ApiEndpoint.TrimEnd('/')
$escapedSmart = $smartctl.Replace('\', '\\')
$config = @"
version: 1
host:
  id: "$HostId"
api:
  endpoint: '$ApiEndpoint'
commands:
  metrics_smartctl_bin: '$escapedSmart'
"@
$configPath = Join-Path $destDir 'collector.yaml'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($configPath, $config, $utf8)

# Disable-PnpDevice in the S4U background session returns Generic failure.
# The same call succeeds in an elevated desktop session, so the on/off and
# SMART tasks have to run there: Interactive, not S4U. An Interactive task
# starts only when its own account is logged on. Registering it as this
# elevated window's account left it as Pilot while the desktop stayed
# SURFACE\HTPC, and schtasks /Run then returned success without starting the
# task.
# WSL's schtasks runs as the console user and is granted read and run.
$caller = (Get-CimInstance Win32_ComputerSystem).UserName
if (-not $caller) { throw 'no console user; pass is not available, log on to the Surface desktop and run this again' }
# HighestAvailable elevates only members of Administrators. A standard user
# stays unelevated, and Disable-PnpDevice then fails both devices with
# Generic failure.
$callerSid = (New-Object System.Security.Principal.NTAccount($caller)).Translate([System.Security.Principal.SecurityIdentifier]).Value
$adminSids = @(Get-LocalGroupMember -Group Administrators | ForEach-Object { $_.SID.Value })
if ($adminSids -notcontains $callerSid) {
    throw ($caller + ' is not an administrator, so this task cannot disable the backup disk')
}
# ProgramData gives Users read only. The on/off task runs as the console user,
# so it cannot replace last-error.txt and a new failure leaves the previous text in place.
& icacls.exe $destDir /grant ($caller + ':(OI)(CI)M') | Out-Null
$errorFile = Join-Path $destDir 'last-error.txt'
if (Test-Path -LiteralPath $errorFile) { Remove-Item -LiteralPath $errorFile -Force }

function Grant-TaskRun {
    param(
        $Folder,
        [string]$Name,
        [string]$Sid
    )
    $task = $Folder.GetTask($Name)
    $sddl = $task.GetSecurityDescriptor(0xF)
    if ($sddl -like ('*' + $Sid + '*')) { return }
    # GRGX is generic read plus generic execute: schtasks /Query and /Run.
    # The flags argument must be 0. 0x4 is a GetSecurityDescriptor flag and is rejected here.
    $ace = '(A;;GRGX;;;' + $Sid + ')'
    $sddl = $sddl.Replace('D:(', ('D:' + $ace + '('))
    $task.SetSecurityDescriptor($sddl, 0)
}

$principal = New-ScheduledTaskPrincipal -UserId $caller -LogonType Interactive -RunLevel Highest
# Demand start is the default. Windows PowerShell 5.1 has -DisallowDemandStart, not -AllowDemandStart.
$settings = New-ScheduledTaskSettingsSet -DontStopOnIdleEnd -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
# wscript Run style 0 starts PowerShell with no console. powershell.exe
# -WindowStyle Hidden still flashes a window in this Interactive session.
$exe = 'C:\Windows\System32\wscript.exe'
$scheduler = New-Object -ComObject Schedule.Service
$scheduler.Connect()
$folder = $scheduler.GetFolder('\')

$smartSettings = New-ScheduledTaskSettingsSet -DontStopOnIdleEnd -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 18)

foreach ($pair in @(@('BackupDiskOn', 'On'), @('BackupDiskOff', 'Off'), @('BackupDiskSmartShort', 'SmartShort'), @('BackupDiskSmartLong', 'SmartLong'))) {
    $name = $pair[0]
    $actionName = $pair[1]
    $arg = '//nologo C:\ProgramData\backup-disk\backup-disk.vbs ' + $actionName
    $action = New-ScheduledTaskAction -Execute $exe -Argument $arg
    $taskSettings = $settings
    if ($actionName -like 'Smart*') { $taskSettings = $smartSettings }
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $taskSettings -Force | Out-Null
    Grant-TaskRun -Folder $folder -Name $name -Sid $callerSid
    Write-Output ("registered " + $name + " as " + $caller)
}

# The collector reads physical disks. SYSTEM can do that without an interactive
# logon. The on/off tasks stay Interactive because Disable-PnpDevice cannot.
Unregister-ScheduledTask -TaskName 'Scrutiny Collector' -Confirm:$false -ErrorAction SilentlyContinue
$collectArg = "-NoProfile -ExecutionPolicy Bypass -File `"$invoke`" -ConfigPath `"$configPath`""
$collectAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $collectArg
$collectSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$collectPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'BackupDiskCollect' -Action $collectAction -Principal $collectPrincipal -Settings $collectSettings -Force | Out-Null
Grant-TaskRun -Folder $folder -Name 'BackupDiskCollect' -Sid $callerSid
Write-Output 'registered BackupDiskCollect as SYSTEM'

Write-Output 'Surface disk tasks are installed. D: was not powered off.'
Write-Output ("  Scrutiny endpoint: " + $ApiEndpoint)
Write-Output ("  Host id: " + $HostId)
