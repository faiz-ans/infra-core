# Pin SURFACE_UPSTREAM on the Ethernet NIC. Safe to re-run. Does not restart Docker.
# Do not rely on a router DHCP reservation: that lease is typically the Wi-Fi
# MAC. Ethernet is a different NIC and will not get SURFACE_UPSTREAM while the
# Wi-Fi reservation holds it. Caddy, OMV NFS, and Pi-hole :53 all key off
# that address.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap\surface\surface-lan-static.ps1
#   powershell -ExecutionPolicy Bypass -File bootstrap\surface\surface-lan-static.ps1 -HtpcIp 192.168.1.111 -NasIp 192.168.1.110 -Gateway 192.168.1.1
#
# Run elevated. Plug Ethernet first. Releases SURFACE_UPSTREAM from Wi-Fi so the
# two NICs do not share it. Disables Wi-Fi by default so copies use the wire.
#Requires -Version 5.1
#Requires -RunAsAdministrator
param(
  [string]$HtpcIp = "192.168.1.111",
  [string]$NasIp = "192.168.1.110",
  [string]$Gateway = "192.168.1.1",
  [int]$PrefixLength = 24,
  [string]$InterfaceAlias = "",
  [switch]$KeepWifi
)

$ErrorActionPreference = "Stop"

function Test-Ipv4([string]$ip) {
  return $ip -match '^\d{1,3}(\.\d{1,3}){3}$'
}

foreach ($pair in @(
    @{ N = "HtpcIp"; V = $HtpcIp },
    @{ N = "NasIp"; V = $NasIp },
    @{ N = "Gateway"; V = $Gateway }
  )) {
  if (-not (Test-Ipv4 $pair.V)) {
    Write-Error "$($pair.N) must be an IPv4 address."
  }
}

function Test-IsWifi($nic) {
  if ($nic.PhysicalMediaType -eq "Native 802.11") { return $true }
  if ($nic.Name -match '(?i)^wi-?fi') { return $true }
  if ($nic.InterfaceDescription -match '(?i)wireless|wi-?fi|802\.11') { return $true }
  return $false
}

function Test-IsEthernet($nic) {
  if (Test-IsWifi $nic) { return $false }
  if ($nic.PhysicalMediaType -eq "802.3") { return $true }
  if ($nic.MediaType -eq "802.3") { return $true }
  if ($nic.Name -match '(?i)ethernet') { return $true }
  return $false
}

function Get-NicIpv4([string]$alias) {
  Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "169.254.*" }
}

$physical = @(Get-NetAdapter -Physical)
$ethernet = @($physical | Where-Object { Test-IsEthernet $_ })
$wifi = @($physical | Where-Object { Test-IsWifi $_ })

if ($InterfaceAlias) {
  $ethernet = @($ethernet | Where-Object { $_.Name -eq $InterfaceAlias })
  if ($ethernet.Count -eq 0) {
    Write-Error "No Ethernet NIC named '$InterfaceAlias'. $((Get-NetAdapter -Physical | ForEach-Object Name) -join ', ')"
  }
}

if ($ethernet.Count -eq 0) {
  Write-Error "No Ethernet NIC found. Plug the cable / enable the adapter."
}

$up = @($ethernet | Where-Object { $_.Status -eq "Up" })
if ($up.Count -eq 1) {
  $eth = $up[0]
} elseif ($up.Count -gt 1) {
  $eth = $up | Sort-Object -Property LinkSpeed -Descending | Select-Object -First 1
  Write-Host "htpc-lan-static: several Ethernet NICs are Up; using $($eth.Name) ($($eth.LinkSpeed))."
} else {
  $eth = $ethernet | Select-Object -First 1
}

if ($eth.Status -eq "Disabled") {
  Write-Host "htpc-lan-static: enabling $($eth.Name)"
  Enable-NetAdapter -Name $eth.Name -Confirm:$false
  $eth = Get-NetAdapter -Name $eth.Name
}

if ($eth.Status -ne "Up") {
  Write-Error "Ethernet '$($eth.Name)' is $($eth.Status). Plug the cable, then re-run."
}

$alias = $eth.Name
$dnsWant = @($NasIp, $HtpcIp)

function Test-AlreadyPinned {
  $if = Get-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4
  if ($if.Dhcp -ne "Disabled") { return $false }
  $addrs = @(Get-NicIpv4 $alias | ForEach-Object IPAddress)
  if ($addrs -notcontains $HtpcIp) { return $false }
  $gw = Get-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $gw -or $gw.NextHop -ne $Gateway) { return $false }
  $dns = @((Get-DnsClientServerAddress -InterfaceAlias $alias -AddressFamily IPv4).ServerAddresses)
  if ($dns.Count -lt 2) { return $false }
  if ($dns[0] -ne $NasIp -or $dns[1] -ne $HtpcIp) { return $false }
  return $true
}

function Disable-WifiHoldingHtpc {
  foreach ($w in $wifi) {
    $holds = @(Get-NicIpv4 $w.Name | Where-Object { $_.IPAddress -eq $HtpcIp })
    $active = $w.Status -eq "Up"
    if (-not $KeepWifi) {
      if ($w.Status -ne "Disabled") {
        Write-Host "htpc-lan-static: disabling Wi-Fi $($w.Name) (was $($w.Status))"
        Disable-NetAdapter -Name $w.Name -Confirm:$false
      }
      continue
    }
    if ($holds.Count -gt 0) {
      Write-Host "htpc-lan-static: taking $HtpcIp off Wi-Fi $($w.Name)"
      $holds | Remove-NetIPAddress -Confirm:$false
    }
    if ($active) {
      Set-NetIPInterface -InterfaceAlias $w.Name -AddressFamily IPv4 -InterfaceMetric 75
    }
  }
}

function Set-EthernetStatic {
  Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Dhcp Disabled -InterfaceMetric 10

  Get-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue

  Get-NicIpv4 $alias |
    Where-Object { $_.IPAddress -ne $HtpcIp } |
    ForEach-Object { Remove-NetIPAddress -InterfaceAlias $alias -IPAddress $_.IPAddress -Confirm:$false }

  $have = @(Get-NicIpv4 $alias | Where-Object { $_.IPAddress -eq $HtpcIp })
  if ($have.Count -eq 0) {
    New-NetIPAddress -InterfaceAlias $alias -IPAddress $HtpcIp -PrefixLength $PrefixLength -DefaultGateway $Gateway |
      Out-Null
  } elseif (-not (Get-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue)) {
    New-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" -NextHop $Gateway | Out-Null
  }

  Set-DnsClientServerAddress -InterfaceAlias $alias -ServerAddresses $dnsWant
  try {
    Set-NetConnectionProfile -InterfaceAlias $alias -NetworkCategory Private
  } catch {
    Write-Host "htpc-lan-static: could not set Private profile ($($_.Exception.Message))"
  }
}

Disable-WifiHoldingHtpc

if (Test-AlreadyPinned) {
  Write-Host "htpc-lan-static: $alias already $HtpcIp/$PrefixLength via $Gateway (manual)."
} else {
  Write-Host "htpc-lan-static: $alias -> $HtpcIp/$PrefixLength via $Gateway (manual)"
  Set-EthernetStatic
}

$live = @(Get-NicIpv4 $alias | Where-Object { $_.IPAddress -eq $HtpcIp })
if ($live.Count -eq 0) {
  Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 | Format-Table -AutoSize
  Write-Error "htpc-lan-static: $HtpcIp is not on $alias after apply."
}

$def = Get-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
  Select-Object -First 1
if (-not $def -or $def.NextHop -ne $Gateway) {
  Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Format-Table -AutoSize
  Write-Error "htpc-lan-static: default via $Gateway on $alias missing."
}

Write-Host "htpc-lan-static: $alias $HtpcIp/$PrefixLength via $Gateway, DNS $($dnsWant -join ', ')."
Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike "169.254.*" } |
  Format-Table InterfaceAlias, IPAddress, PrefixLength, PrefixOrigin -AutoSize
Get-NetRoute -InterfaceAlias $alias -DestinationPrefix "0.0.0.0/0" |
  Format-Table InterfaceAlias, NextHop, RouteMetric -AutoSize

# ping.exe: Test-Connection (Win32_PingStatus) throws "Generic failure" on a
# NIC that just went static, even with -Quiet, and Stop turns that into a crash.
$pingOk = $false
for ($i = 0; $i -lt 3; $i++) {
  & ping.exe -n 1 -w 1000 $NasIp | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $pingOk = $true
    break
  }
  Start-Sleep -Seconds 1
}
if ($pingOk) {
  Write-Host "htpc-lan-static: ping $NasIp ok."
} else {
  Write-Host "htpc-lan-static: ping $NasIp failed (ICMP may be off). Check the cable / gateway."
}

Write-Host "Delete the Wi-Fi DHCP reservation for $HtpcIp in the router. Do not add an Ethernet reservation; this static address is the source of truth."
if (-not $KeepWifi) {
  Write-Host "Wi-Fi is disabled. Re-enable later with: Enable-NetAdapter -Name 'Wi-Fi'"
}
Write-Host "SURFACE_UPSTREAM stays $HtpcIp. If pihole-mantle cannot bind :53, re-apply that Quadlet."
exit 0
