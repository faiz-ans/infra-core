# Park the Surface backup disk by disabling its DiskDrive node, then the USB
# mass-storage device that powers it. Disabling only the disk removes D: and
# the platter spins back up. Bring it back by enabling the USB device first,
# then the DiskDrive node. Hubs and host controllers are never changed. The
# saved disk id is the disk behind D: at install time. It must be a USB disk
# and it must not be the disk that holds C:.
# ASCII only: Windows PowerShell 5.1 misreads UTF-8 punctuation.
#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('On', 'Off', 'Status', 'Save', 'SmartShort', 'SmartLong', 'SmartStatus')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = 'C:\ProgramData\backup-disk'
$IdFile = Join-Path $Root 'instance-id.txt'
$PowerFile = Join-Path $Root 'power-id.txt'
$ErrorFile = Join-Path $Root 'last-error.txt'
$SmartFile = Join-Path $Root 'smart.txt'
$Smartctl = 'C:\Program Files\smartmontools\bin\smartctl.exe'

function Write-Token {
    param([string]$Token)
    Write-Output $Token
}

function Set-Failure {
    param([string]$Message)
    $one = ($Message -replace '[\r\n]+', ' ').Trim()
    if ($one.Length -gt 300) { $one = $one.Substring(0, 300) }
    try {
        New-Item -ItemType Directory -Force -Path $Root | Out-Null
        Set-Content -LiteralPath $ErrorFile -Value $one -Encoding ASCII
    } catch {
    }
    Write-Token ("error: " + $one)
}

function Get-SystemDiskNumber {
    return (Get-Partition -DriveLetter C | Select-Object -First 1).DiskNumber
}

function Get-DiskByInstance {
    param([string]$InstanceId)
    $win = Get-CimInstance Win32_DiskDrive | Where-Object { $_.PNPDeviceID -eq $InstanceId } | Select-Object -First 1
    if (-not $win) { return $null }
    return Get-Disk -Number $win.Index
}

function Save-Identity {
    param([string]$InstanceId)
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    Set-Content -LiteralPath $IdFile -Value $InstanceId -Encoding ASCII
}

function Find-Identity {
    $system = Get-SystemDiskNumber
    $part = Get-Partition -DriveLetter D -ErrorAction SilentlyContinue
    if (-not $part) { return $null }
    if ($part.DiskNumber -eq $system) { throw 'D: is the system disk' }
    $disk = Get-Disk -Number $part.DiskNumber
    if ($disk.BusType -ne 'USB' -and $disk.BusType -ne 'External') {
        throw ('D: bus is ' + $disk.BusType + ', not USB')
    }
    $win = Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $part.DiskNumber } | Select-Object -First 1
    if (-not $win -or -not $win.PNPDeviceID) { throw 'D: has no PnP device id' }
    if ($win.PNPDeviceID -eq (Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $system } | Select-Object -ExpandProperty PNPDeviceID -First 1)) {
        throw 'D: PnP id matches the system disk'
    }
    return [string]$win.PNPDeviceID
}

function Read-Identity {
    if (-not (Test-Path -LiteralPath $IdFile)) { return $null }
    $id = (Get-Content -LiteralPath $IdFile -Raw).Trim()
    if (-not $id) { return $null }
    return $id
}

function Save-PowerId {
    param([string]$InstanceId)
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    Set-Content -LiteralPath $PowerFile -Value $InstanceId -Encoding ASCII
}

function Read-PowerId {
    if (-not (Test-Path -LiteralPath $PowerFile)) { return $null }
    $id = (Get-Content -LiteralPath $PowerFile -Raw).Trim()
    if (-not $id) { return $null }
    return $id
}

function Get-DiskSerial {
    param([string]$DiskId)
    $parts = $DiskId -split '\\'
    if ($parts.Length -lt 3) { return $null }
    $serial = ($parts[2] -split '&')[0]
    if (-not $serial) { return $null }
    return $serial
}

function Get-PowerParent {
    param([string]$DiskId)
    $serial = Get-DiskSerial $DiskId
    if (-not $serial) { throw 'disk id has no serial' }
    $parent = (Get-PnpDeviceProperty -InstanceId $DiskId -KeyName 'DEVPKEY_Device_Parent').Data
    if (-not $parent) { throw 'disk has no parent device' }
    $parent = [string]$parent
    $dev = Get-PnpDevice -InstanceId $parent -ErrorAction SilentlyContinue
    if (-not $dev) { throw 'disk parent is not present' }
    if ($dev.Class -ne 'USB') { throw ('disk parent class is ' + $dev.Class) }
    if ($parent -notlike 'USB\VID_*') { throw ('refusing to power ' + $parent) }
    if ($parent -notlike ('*' + $serial + '*')) { throw ('parent does not match disk serial ' + $serial) }
    if ($dev.FriendlyName -match 'Hub|Host Controller|xHCI|eXtensible') {
        throw ('refusing to power ' + $dev.FriendlyName)
    }
    return $parent
}

function Resolve-PowerId {
    param(
        [string]$DiskId,
        [switch]$Persist
    )
    $disk = Get-PnpDevice -InstanceId $DiskId -ErrorAction SilentlyContinue
    if ($disk -and $disk.Class -eq 'DiskDrive') {
        $power = Get-PowerParent $DiskId
        if ($Persist) { Save-PowerId $power }
        return $power
    }
    $saved = Read-PowerId
    if ($saved) { return $saved }
    throw 'USB power device is not saved and the disk is not online'
}

function Assert-NotSystem {
    param([string]$InstanceId)
    $system = Get-SystemDiskNumber
    $sys = Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $system } | Select-Object -First 1
    if ($sys -and $sys.PNPDeviceID -eq $InstanceId) { throw 'refusing to power the system disk' }
}

function Repair-Letter {
    param([string]$InstanceId)
    $win = Get-CimInstance Win32_DiskDrive | Where-Object { $_.PNPDeviceID -eq $InstanceId } | Select-Object -First 1
    if (-not $win) { return $false }
    $part = Get-Partition -DiskNumber $win.Index | Where-Object { $_.Type -ne 'Reserved' -and $_.Size -gt 1GB } | Select-Object -First 1
    if (-not $part) { return $false }
    if ($part.DriveLetter -eq 'D') { return $true }
    $taken = Get-Partition -DriveLetter D -ErrorAction SilentlyContinue
    if ($taken) { throw 'D: belongs to a different disk' }
    Set-Partition -DiskNumber $part.DiskNumber -PartitionNumber $part.PartitionNumber -NewDriveLetter D
    return $true
}

function Test-Ready {
    return Test-Path -LiteralPath 'D:\restic'
}

function Write-SmartToken {
    param([string]$Token)
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    Set-Content -LiteralPath $SmartFile -Value $Token -Encoding ASCII
}

function Get-BackupDiskNumber {
    param([string]$InstanceId)
    Assert-NotSystem $InstanceId
    $win = Get-CimInstance Win32_DiskDrive | Where-Object { $_.PNPDeviceID -eq $InstanceId } | Select-Object -First 1
    if (-not $win) { throw 'backup disk is not online' }
    if ($win.Index -eq (Get-SystemDiskNumber)) { throw 'refusing the system disk' }
    return [int]$win.Index
}

function Invoke-Smartctl {
    param([string[]]$SmartArgs)
    if (-not (Test-Path -LiteralPath $Smartctl)) { throw 'smartctl is missing' }
    $out = & $Smartctl @SmartArgs 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Text = $out }
}

function Get-SelfTestState {
    param(
        [string]$Text,
        [int]$Code
    )
    if ($Text -match 'routine in progress|of test remaining') { return 'running' }
    if ($Text -match 'previous self-test routine completed|completed without error|was aborted|interrupted by') { return 'done' }
    if ($Code -ne 0) { return 'error' }
    return 'unknown'
}

function Get-SmartDevice {
    param([int]$Number)
    # smartctl --scan-open names physical drive N as /dev/sdX and opens the
    # backup disk as -d sat. \\.\PhysicalDriveN returns "Invalid argument".
    return '/dev/sd' + [char](97 + $Number)
}

function Read-SelfTestState {
    param([string]$Device)
    $info = Invoke-Smartctl @('-d', 'sat', '-c', $Device)
    return (Get-SelfTestState -Text $info.Text -Code $info.Code)
}

function Start-SelfTest {
    param(
        [string]$InstanceId,
        [string]$Mode
    )
    $number = Get-BackupDiskNumber $InstanceId
    $device = Get-SmartDevice $number
    Write-SmartToken 'running'
    $started = Invoke-Smartctl @('-d', 'sat', '-t', $Mode, $device)
    if ($started.Code -ne 0) {
        Write-SmartToken 'error'
        $detail = ($started.Text -replace '[\r\n]+', ' ').Trim()
        throw ('smartctl -d sat -t ' + $Mode + ' ' + $device + ' failed: ' + $detail)
    }
    $deadline = (Get-Date).AddHours(18)
    if ($Mode -eq 'short') { $deadline = (Get-Date).AddMinutes(30) }
    do {
        Start-Sleep -Seconds 30
        $state = Read-SelfTestState $device
        if ($state -eq 'done') {
            Write-SmartToken 'done'
            return
        }
        if ($state -eq 'error') {
            Write-SmartToken 'error'
            throw 'smartctl could not read the self-test'
        }
    } while ((Get-Date) -lt $deadline)
    Write-SmartToken 'error'
    throw 'self-test did not finish'
}

try {
    if ($Action -eq 'SmartStatus') {
        if (-not (Test-Path -LiteralPath $SmartFile)) {
            Write-Token 'idle'
            exit 0
        }
        $token = (Get-Content -LiteralPath $SmartFile -Raw).Trim()
        if ($token -ne 'running' -and $token -ne 'done' -and $token -ne 'error') { $token = 'idle' }
        Write-Token $token
        exit 0
    }

    if ($Action -eq 'Save') {
        $id = Find-Identity
        if (-not $id) { throw 'D: is not online' }
        Save-Identity $id
        Save-PowerId (Get-PowerParent $id)
        Write-Token 'saved'
        exit 0
    }

    $id = Read-Identity
    if (-not $id) {
        $id = Find-Identity
        if ($id) { Save-Identity $id }
    }
    if (-not $id) { throw 'D: is offline and no saved disk id exists' }
    Assert-NotSystem $id

    if ($Action -eq 'SmartShort' -or $Action -eq 'SmartLong') {
        $mode = 'short'
        if ($Action -eq 'SmartLong') { $mode = 'long' }
        Start-SelfTest $id $mode
        Write-Token 'done'
        exit 0
    }

    $power = Resolve-PowerId $id -Persist:($Action -ne 'Status')
    $usb = Get-PnpDevice -InstanceId $power -ErrorAction SilentlyContinue
    if (-not $usb) { throw 'USB power device is not present' }
    $disk = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue

    if ($Action -eq 'Status') {
        # The spindle stays powered until the USB device itself is disabled.
        # A disabled DiskDrive node removes D: and then the platter spins back up.
        if ($usb.Status -ne 'OK') {
            Write-Token 'off'
            exit 0
        }
        if (-not $disk -or $disk.Status -ne 'OK') {
            Write-Token 'pending'
            exit 0
        }
        if ((Test-Ready) -or ((Repair-Letter $id) -and (Test-Ready))) {
            if (Test-Path -LiteralPath $ErrorFile) {
                Remove-Item -LiteralPath $ErrorFile -Force -ErrorAction SilentlyContinue
            }
            Write-Token 'ready'
            exit 0
        }
        Write-Token 'pending'
        exit 0
    }

    if ($Action -eq 'On') {
        if (Test-Path -LiteralPath $ErrorFile) { Remove-Item -LiteralPath $ErrorFile -Force }
        if ($usb.Status -ne 'OK') {
            Enable-PnpDevice -InstanceId $power -Confirm:$false
        }
        $disk = Get-PnpDevice -InstanceId $id -ErrorAction SilentlyContinue
        if (-not $disk -or $disk.Status -ne 'OK') {
            Enable-PnpDevice -InstanceId $id -Confirm:$false
        }
        $deadline = (Get-Date).AddSeconds(90)
        do {
            if ((Repair-Letter $id) -and (Test-Ready)) {
                Write-Token 'ready'
                exit 0
            }
            Start-Sleep -Seconds 2
        } while ((Get-Date) -lt $deadline)
        throw 'D:\restic did not appear'
    }

    if ($Action -eq 'Off') {
        # Record the instance id. Disable-PnpDevice's own message is only
        # "Generic failure", which does not say which device was refused.
        $failures = @()
        if ($disk -and $disk.Status -eq 'OK') {
            try { Disable-PnpDevice -InstanceId $id -Confirm:$false }
            catch { $failures += ('disk ' + $id + ' ' + $_.Exception.Message) }
        }
        $usb = Get-PnpDevice -InstanceId $power -ErrorAction SilentlyContinue
        if (-not $usb) { $failures += ('usb ' + $power + ' is not present') }
        elseif ($usb.Status -eq 'OK') {
            try { Disable-PnpDevice -InstanceId $power -Confirm:$false }
            catch { $failures += ('usb ' + $power + ' ' + $_.Exception.Message) }
        }
        $usb = Get-PnpDevice -InstanceId $power -ErrorAction SilentlyContinue
        if ((-not $usb) -or ($usb.Status -eq 'OK')) {
            if ($failures.Count -eq 0) { $failures += ('usb ' + $power + ' stayed enabled') }
            throw ($failures -join ' | ')
        }
        if (Test-Path -LiteralPath $ErrorFile) { Remove-Item -LiteralPath $ErrorFile -Force }
        Write-Token 'off'
        exit 0
    }
} catch {
    Set-Failure $_.Exception.Message
    exit 1
}
