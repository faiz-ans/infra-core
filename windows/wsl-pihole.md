# WSL2 Pi-hole on the LAN

SET installs Pi-hole inside WSL on port **15353**. It does not publish port **53** on a WSL host. Mirrored networking never delivers LAN port 53 into the guest, so a router cannot use that Pi-hole until Windows forwards port 53.

Do this on the Windows PC that runs the WSL Pi-hole, after SET has started Pi-hole. List that host second in DHCP. The ingress host (Core) stays first.

```
LAN client :53
        │
        ▼
Windows dnsproxy  0.0.0.0:53
        │  127.0.0.1:15353
        ▼
WSL Pi-hole :15353
        │
        ▼
same answers as the ingress Pi-hole (home.lan → ingress IP, plus public DNS)
```

Point dnsproxy at **127.0.0.1:15353**. The host LAN address (for example `192.168.1.111:15353`) is the Windows machine itself; that query never enters WSL.

## 1. WSL can be reached on localhost

In `%UserProfile%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
localhostForwarding=true

[experimental]
hostAddressLoopback=true
```

Elevated PowerShell:

```powershell
wsl --shutdown
```

Open the WSL terminal again and wait until Pi-hole is up (`podman ps` shows `pi-hole`).

Inside WSL:

```bash
dig +short @127.0.0.1 -p 15353 dash.home.lan
```

On Windows:

```powershell
Resolve-DnsName dash.home.lan -Server 127.0.0.1 -Port 15353 -Type A -DnsOnly
```

Both must return the ingress host address. If Windows times out, the `.wslconfig` block above is not in effect yet.

## 2. Windows listens on port 53

Download the Windows amd64 build of AdGuard [dnsproxy](https://github.com/AdguardTeam/dnsproxy/releases) and keep `dnsproxy.exe` in a stable folder, for example `C:\Tools\dnsproxy\`.

Elevated PowerShell, leave the window open for the test:

```powershell
cd C:\Tools\dnsproxy
.\dnsproxy.exe -l 0.0.0.0 -p 53 -u 127.0.0.1:15353 --cache
```

Allow the LAN to reach that process:

```powershell
New-NetFirewallRule -DisplayName 'WSL Pi-hole DNS UDP 53' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 53 -Profile Any
New-NetFirewallRule -DisplayName 'WSL Pi-hole DNS TCP 53' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 53 -Profile Any
```

From another machine, using the WSL host's LAN IP from `site.yaml`:

```bash
dig +short @192.168.1.111 dash.home.lan
dig +short @192.168.1.111 google.com
```

The first answer is the ingress IP. The second is a public address.

## 3. Keep it across reboot

Elevated PowerShell. Change the exe path if you did not use `C:\Tools\dnsproxy\`.

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Tools\dnsproxy\dnsproxy.exe' `
  -Argument '-l 0.0.0.0 -p 53 -u 127.0.0.1:15353 --cache'
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'SiteWslPiholeDns' -Action $action -Trigger $trigger -Principal $principal -Force
Start-ScheduledTask -TaskName 'SiteWslPiholeDns'
```

Stop the foreground `dnsproxy.exe` from step 2 before starting the task, or port 53 is already taken.

WSL has to be running before the task can reach Pi-hole. A query that arrives first fails until the guest and the Pi-hole container are up.

## 4. Router

DHCP DNS, in this order:

1. Ingress host (Core), port 53
2. This Windows host, port 53

Clients try the first server and use the second after a timeout. The Windows forwarder is the backup: it is down when Windows, dnsproxy, WSL, or Pi-hole is down.

## 5. Other ports published from WSL

Mirrored networking does not deliver a LAN TCP port into WSL unless a Hyper-V firewall rule allows it. DNS above is port 53 on Windows. These listeners are inside WSL, so Core's Caddy cannot reach them until the rule exists:

| Service | Port |
|---|---|
| Glances | 61208 |
| Immich | 2283 |
| Pi-hole web | 8088 |

Elevated PowerShell. Use the same `VMCreatorId` as the existing WSL rules (`Get-NetFirewallHyperVRule`). If New-NetFirewallHyperVRule says the file already exists, enable that rule instead of creating it.

```powershell
$wsl = (Get-NetFirewallHyperVRule | Select-Object -First 1 -ExpandProperty VMCreatorId)
foreach ($port in 61208, 2283, 8088) {
  $name = "WSL-TCP-$port"
  if (Get-NetFirewallHyperVRule -Name $name -ErrorAction SilentlyContinue) {
    Enable-NetFirewallHyperVRule -Name $name
  } else {
    New-NetFirewallHyperVRule -Name $name -DisplayName $name -Direction Inbound -VMCreatorId $wsl -Protocol TCP -LocalPorts $port -Action Allow
  }
}
```
