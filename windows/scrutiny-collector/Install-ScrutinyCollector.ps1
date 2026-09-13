#Requires -Version 5.1
<#
.SYNOPSIS
  Install the AnalogJ Scrutiny Windows collector and a daily Scheduled Task.

.PARAMETER ApiEndpoint
  Scrutiny hub on Core, e.g. http://192.168.1.110:8080 (NAS_LAN_IP). Not HTTPS.

.PARAMETER HostId
  Label in the Scrutiny UI for this machine's disks.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiEndpoint,

    [string]$HostId = 'periphery',

    [string]$InstallDir = $PSScriptRoot,

    [string]$TaskName = 'Scrutiny Collector'
)

$ErrorActionPreference = 'Stop'

$ApiEndpoint = $ApiEndpoint.TrimEnd('/')
$smartctl = 'C:\Program Files\smartmontools\bin\smartctl.exe'
if (-not (Test-Path -LiteralPath $smartctl)) {
    throw "smartctl not found at $smartctl. Install smartmontools.smartmontools (winget / windows/packages.json)."
}

$exeName = 'scrutiny-collector-metrics-windows-amd64.exe'
$exe = Join-Path $InstallDir $exeName
if (-not (Test-Path -LiteralPath $exe)) {
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/AnalogJ/scrutiny/releases/latest' -Headers @{
        'User-Agent' = 'infra-core-scrutiny-collector'
    }
    $asset = $release.assets | Where-Object { $_.name -eq $exeName } | Select-Object -First 1
    if (-not $asset) {
        throw "GitHub release has no $exeName asset."
    }
    Write-Host "Downloading $($asset.browser_download_url)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $exe -UseBasicParsing
}

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
$configPath = Join-Path $InstallDir 'collector.yaml'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($configPath, $config, $utf8)

$invoke = Join-Path $InstallDir 'Invoke-ScrutinyCollector.ps1'
if (-not (Test-Path -LiteralPath $invoke)) {
    throw "Missing $invoke"
}
$invoke = (Resolve-Path -LiteralPath $invoke).Path
$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$invoke`" -ConfigPath `"$configPath`""

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
$triggerDaily = New-ScheduledTaskTrigger -Daily -At 6:15am
$triggerStart = New-ScheduledTaskTrigger -AtStartup
$triggerStart.Delay = 'PT2M'
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId 'SYSTEM' `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($triggerDaily, $triggerStart) `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Registered task '$TaskName'."
Write-Host "  Endpoint: $ApiEndpoint"
Write-Host "  Host id: $HostId"
Write-Host "  Config: $configPath"
Write-Host "Run once now: Start-ScheduledTask -TaskName '$TaskName'"
