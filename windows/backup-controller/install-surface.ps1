# Register the elevated tasks that enable and disable the D: backup disk.
# Run once from an elevated PowerShell on Surface, while D: is online.
# GET/SET does not run this.
#Requires -Version 5.1
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'backup-disk.ps1'
$vbsSrc = Join-Path $PSScriptRoot 'backup-disk.vbs'
if (-not (Test-Path -LiteralPath $src)) { throw "missing $src" }
if (-not (Test-Path -LiteralPath $vbsSrc)) { throw "missing $vbsSrc" }

$destDir = 'C:\ProgramData\backup-disk'
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$dest = Join-Path $destDir 'backup-disk.ps1'
$vbs = Join-Path $destDir 'backup-disk.vbs'
Copy-Item -LiteralPath $src -Destination $dest -Force
Copy-Item -LiteralPath $vbsSrc -Destination $vbs -Force

& $dest -Action Save

# Disable-PnpDevice in the S4U background session returns Generic failure.
# The same call succeeds in an elevated desktop session, so the task has to
# run there: Interactive, not S4U. An Interactive task starts only when its
# own account is logged on. Registering it as this elevated window's account
# left it as Pilot while the desktop stayed SURFACE\HTPC, and schtasks /Run
# then returned success without starting the task.
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
# ProgramData gives Users read only. The task runs as the console user, so it
# cannot replace last-error.txt and a new failure leaves the previous text in place.
& icacls.exe $destDir /grant ($caller + ':(OI)(CI)M') | Out-Null
$errorFile = Join-Path $destDir 'last-error.txt'
if (Test-Path -LiteralPath $errorFile) { Remove-Item -LiteralPath $errorFile -Force }
$principal = New-ScheduledTaskPrincipal -UserId $caller -LogonType Interactive -RunLevel Highest
# Demand start is the default. Windows PowerShell 5.1 has -DisallowDemandStart, not -AllowDemandStart.
$settings = New-ScheduledTaskSettingsSet -DontStopOnIdleEnd -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
# wscript Run style 0 starts PowerShell with no console. powershell.exe
# -WindowStyle Hidden still flashes a window in this Interactive session.
$exe = 'C:\Windows\System32\wscript.exe'
$scheduler = New-Object -ComObject Schedule.Service
$scheduler.Connect()
$folder = $scheduler.GetFolder('\')

foreach ($pair in @(@('BackupDiskOn', 'On'), @('BackupDiskOff', 'Off'))) {
    $name = $pair[0]
    $actionName = $pair[1]
    $arg = '//nologo C:\ProgramData\backup-disk\backup-disk.vbs ' + $actionName
    $action = New-ScheduledTaskAction -Execute $exe -Argument $arg
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
    $task = $folder.GetTask($name)
    $sddl = $task.GetSecurityDescriptor(0xF)
    if ($sddl -notlike ('*' + $callerSid + '*')) {
        # GRGX is generic read plus generic execute: schtasks /Query and /Run.
        # The flags argument must be 0. 0x4 is a GetSecurityDescriptor flag and is rejected here.
        $ace = '(A;;GRGX;;;' + $callerSid + ')'
        $sddl = $sddl.Replace('D:(', ('D:' + $ace + '('))
        $task.SetSecurityDescriptor($sddl, 0)
    }
    Write-Output ("registered " + $name + " as " + $caller)
}

Write-Output 'Surface backup disk tasks are installed. D: was not powered off.'
