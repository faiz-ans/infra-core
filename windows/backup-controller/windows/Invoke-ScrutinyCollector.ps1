#Requires -Version 5.1
<#
.SYNOPSIS
  Run one Scrutiny collector pass against the Core hub.

.PARAMETER ConfigPath
  collector.yaml (api endpoint, smartctl path, host id).
#>
[CmdletBinding()]
param(
    [string]$ConfigPath = ''
)

$ErrorActionPreference = 'Stop'
$TokenFile = 'C:\ProgramData\backup-disk\collect.txt'

function Write-CollectToken {
    param([string]$Token)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TokenFile) | Out-Null
    Set-Content -LiteralPath $TokenFile -Value $Token -Encoding ASCII
}

try {
    Write-CollectToken 'running'
    # Windows PowerShell 5.1 leaves $PSScriptRoot empty while binding parameter defaults.
    if (-not $ConfigPath) {
        if (-not $PSScriptRoot) {
            throw 'ConfigPath is empty. Pass -ConfigPath, or launch this file with -File.'
        }
        $ConfigPath = Join-Path $PSScriptRoot 'collector.yaml'
    }
    if (-not $PSScriptRoot) {
        throw 'Collector directory is empty. Launch this file with -File.'
    }
    $exe = Join-Path $PSScriptRoot 'scrutiny-collector-metrics-windows-amd64.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Collector not found: $exe. Run install-surface.ps1 first."
    }
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "Config not found: $ConfigPath"
    }
    & $exe run --config $ConfigPath
    if ($LASTEXITCODE -ne 0) {
        throw "scrutiny collector exited $LASTEXITCODE"
    }
    Write-CollectToken 'done'
} catch {
    try { Write-CollectToken 'error' } catch {}
    throw
}
