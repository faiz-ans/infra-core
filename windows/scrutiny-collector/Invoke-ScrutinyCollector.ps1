#Requires -Version 5.1
<#
.SYNOPSIS
  Run one Scrutiny collector pass against the Core hub.

.PARAMETER ConfigPath
  collector.yaml (api endpoint, smartctl path, host id).
#>
[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'collector.yaml')
)

$ErrorActionPreference = 'Stop'

$exe = Join-Path $PSScriptRoot 'scrutiny-collector-metrics-windows-amd64.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Collector not found: $exe. Run Install-ScrutinyCollector.ps1 first."
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

& $exe run --config $ConfigPath
if ($LASTEXITCODE -ne 0) {
    throw "scrutiny collector exited $LASTEXITCODE"
}
