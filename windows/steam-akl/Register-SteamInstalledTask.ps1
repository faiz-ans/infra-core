#Requires -Version 5.1
<#
.SYNOPSIS
  Register a Scheduled Task that keeps Z:\games\akl-steam-installed in sync.

.DESCRIPTION
  Creates task "AKL Steam Installed Sync" that runs Sync-SteamInstalled.ps1
  at logon (delayed) and every hour while logged on.

.PARAMETER ScriptPath
  Full path to Sync-SteamInstalled.ps1 on this machine.

.PARAMETER OutputDir
  Passed through to the sync script. Default: Z:\games\steam-installed
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string]$OutputDir = 'Z:\games\steam-installed',

    [string]$TaskName = 'AKL Steam Installed Sync'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "Script not found: $ScriptPath"
}

$ScriptPath = (Resolve-Path -LiteralPath $ScriptPath).Path
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" -OutputDir `"$OutputDir`""

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$triggerLogon.Delay = 'PT2M'  # 2 minutes after logon (NAS / Z: may not be ready yet)

$triggerHourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($triggerLogon, $triggerHourly) `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Registered task '$TaskName'."
Write-Host "  Script: $ScriptPath"
Write-Host "  Output: $OutputDir"
Write-Host "Run once now: Start-ScheduledTask -TaskName '$TaskName'"
