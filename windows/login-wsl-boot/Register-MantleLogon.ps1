#Requires -Version 5.1
<#
.SYNOPSIS
  Start mantle (Ubuntu WSL) and the Pi-hole dnsproxy when HTPC signs in.

.DESCRIPTION
  Registers two logon tasks for the HTPC user:
    1. Start-Mantle.ps1 holds `wsl.exe -d Ubuntu -e sleep infinity` so the distro stays up.
    2. dnsproxy listens on 0.0.0.0:53 and forwards to 127.0.0.1:15353.

  Run this from an elevated PowerShell session on surface, signed in as HTPC.
  Replaces the old SYSTEM-at-startup task SiteWslPiholeDns so port 53 is not
  taken before the WSL session exists.
#>
[CmdletBinding()]
param(
    [string]$User = 'HTPC',

    [string]$Distro = 'Ubuntu',

    [string]$DnsproxyExe = 'dnsproxy.exe',

    [string]$TaskName = 'Site Mantle Logon',

    [string]$DnsTaskName = 'Site Mantle Dns'
)

$ErrorActionPreference = 'Stop'

$starter = Join-Path $PSScriptRoot 'Start-Mantle.ps1'
if (-not (Test-Path -LiteralPath $starter)) {
    throw "Missing $starter"
}
if (-not (Test-Path -LiteralPath $DnsproxyExe)) {
    throw "dnsproxy not found at $DnsproxyExe. See windows/wsl-pihole.md."
}

$starter = (Resolve-Path -LiteralPath $starter).Path
$DnsproxyExe = (Resolve-Path -LiteralPath $DnsproxyExe).Path

$boot = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$starter`" -Distro `"$Distro`""
$dns = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-WindowStyle Hidden -NoProfile -Command Start-Process -FilePath '$DnsproxyExe' -ArgumentList '-l 0.0.0.0 -p 53 -u 127.0.0.1:15353 --cache' -WindowStyle Hidden -Wait"

function New-HtpcLogonTrigger {
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
    $trigger.Delay = 'PT30S'
    return $trigger
}

function New-HtpcTaskSettings {
    New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
}

function New-HtpcPrincipal {
    New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
}

Unregister-ScheduledTask -TaskName 'SiteWslPiholeDns' -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $boot `
    -Trigger (New-HtpcLogonTrigger) `
    -Settings (New-HtpcTaskSettings) `
    -Principal (New-HtpcPrincipal) `
    -Force | Out-Null

Register-ScheduledTask `
    -TaskName $DnsTaskName `
    -Action $dns `
    -Trigger (New-HtpcLogonTrigger) `
    -Settings (New-HtpcTaskSettings) `
    -Principal (New-HtpcPrincipal) `
    -Force | Out-Null

Write-Host "Registered '$TaskName' and '$DnsTaskName' for $User at logon."
Write-Host "  Distro: $Distro (held open by wsl.exe)"
Write-Host "  dnsproxy: $DnsproxyExe"
Write-Host "Stop any foreground dnsproxy.exe first, then:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Start-ScheduledTask -TaskName '$DnsTaskName'"
