#Requires -Version 5.1
<#
.SYNOPSIS
  Keep the Ubuntu WSL distro (hostname mantle) running in this Windows session.

.DESCRIPTION
  WSL stops a distro when the last wsl.exe for it exits. A one-shot command
  such as `wsl -e true` boots mantle and then lets it shut down again.
  This script holds one wsl.exe open for the signed-in HTPC session.
#>
[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu'
)

$ErrorActionPreference = 'Stop'

while ($true) {
    $held = Start-Process -FilePath wsl.exe -ArgumentList @('-d', $Distro, '-e', 'sleep', 'infinity') -WindowStyle Hidden -PassThru -Wait
    Write-Host "wsl.exe -d $Distro exited ($($held.ExitCode)); restarting in 5s."
    Start-Sleep -Seconds 5
}
