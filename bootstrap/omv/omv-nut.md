# Core UPS (CyberPower ST625U)

The NAS USB-HID cable goes to a **CyberPower ST625U**. OMV’s NUT plugin (`openmediavault-nut`) monitors it and shuts Core down when the battery is low, so the IronWolf unmounts cleanly instead of dying mid-write.

ST625U is 625 VA / 360 W. Four outlets are battery + surge; four are surge-only. The Pi, HAT, and IronWolf **must** sit on battery-backed outlets. The HID cable is the communication USB, not a charge-only USB-A.

## Install (existing Core)

Copy `bootstrap/` onto Core, then:

```text
sudo bash bootstrap/omv/omv-nut.sh
```

That installs the plugin, writes standalone `usbhid-ups` / `port = auto`, pins CyberPower `vendorid`/`productid` when `lsusb` sees `0764:`, sets `override.battery.charge.low = 30` (cheap CPS HID often reports `0`, which never trips low-battery), and Apply’s NUT. Shutdown mode is **UPS reaches low battery** (`fsd`), with a 30 s cancel window if mains return.

Workbench **Services → UPS** should show Enabled / Standalone / identifier `ups`. **Diagnostics → Services → UPS** (and the dashboard battery widget, if this OMV build has it) is the live monitor.

## Verify

```text
lsusb -d 0764:
upsc ups
systemctl is-active nut-server nut-monitor "nut-driver@ups"
```

You want `ups.status` `OL` or `OL CHRG`, a sane `battery.charge`, and `battery.charge.low` **30** (not `0`). `device.mfr` / `device.model` should look like CPS / ST625U.

Safe on-battery check: pull the wall plug for ~10 s (not the battery-backed load). `upsc ups ups.status` should flip to `OB` (on battery). Plug back; it returns `OL`. That is **not** a shutdown test.

Do **not** run `upsmon -c fsd` unless you intend to halt this host. That command is a real forced shutdown.

## What happens on a real outage

1. Mains fail → `OB`. NUT notifies (syslog / wall). Core stays up.
2. Charge drops to the low threshold (30 %, or the UPS’s own LB flag) → `LB`.
3. After 30 s, if mains are still gone, `shutdown -h +0`. systemd stops Docker, unmounts the IronWolf, powers off.
4. NUT then tells the UPS to drop the load (`offdelay` 60 s on CPS). When AC returns, the UPS restores output (`ondelay` 120 s) and the Pi boots.

Brief blips never reach step 3.

## If it fails

| Symptom | What to do |
|---|---|
| `lsusb` has no `0764:` | HID cable unplugged, or plugged into a charge-only USB-A on the UPS. Re-seat, `sudo bash bootstrap/omv/omv-nut.sh` |
| `nut-driver@ups` restart loop / permission | `udevadm trigger`; confirm the NAS is on the UPS USB HID port. `journalctl -u nut-driver@ups -n 40` |
| `upsc` works but `battery.charge.low` is `0` | CPS quirk. Script sets `override.battery.charge.low = 30`. Re-run the script; `grep charge.low /etc/nut/ups.conf` |
| Status stays `OL` while the UPS is beeping on battery | Some CPS units report `OL+DISCHRG`. Add `onlinedischarge_battery` to the driver textarea, Apply |
| Low battery never shuts down | Confirm shutdown mode is **UPS reaches low battery**, not **UPS goes on battery**. `grep shutdownmode` in Workbench is `fsd`. `journalctl -u nut-monitor` |
| Host stays off after AC returns | NAS was on a surge-only outlet, or CPS `offdelay` cut too fast. Keep `offdelay = 60` / `ondelay = 120`. Pi should power on when the UPS restores output |
| Salt `Failed: 2` / `There is no service named "nut-server"` | Harmless if `nut-server` and `nut-monitor` are active. OMV asks monit to watch NUT before those checks exist. `omv-salt deploy run monit` creates them; the script does that after nut |
| Workbench Apply fails / wrong driver | `/etc/nut/*` is Salt-managed. Change via **Services → UPS** or re-run the script — do not hand-edit |

Leave **Remote monitoring** off unless something on the LAN needs `upsd` on `:3493`. Homepage does not scrape NUT (no PeaNUT stack); use OMV Diagnostics / dashboard.
