# Core cage fan (X1509 PWM)

The Arctic P12 Pro on the 12-pin header (12V / GND / PWM) is driven by a host service from **max(CPU, HDD)**. On this board the usable PWM range is **0–124** (above that the fan spools up and stops). Day-to-day duty is **50** (almost silent, still moves air).

## Install (existing Core)

Copy `bootstrap/` onto Core, then:

```text
sudo bash bootstrap/core-fan.sh
```

If it says the overlay is missing, reboot once. Then:

```text
systemctl status core-fan
journalctl -u core-fan -n 20 --no-pager
```

Idle in the operating range should log `pwm=50/124`.

## Curve (measured on this cage)

| Duty | Noise / air | When |
|---|---|---|
| 50 | Almost inaudible, useful air | CPU ≤ 60 °C and HDD ≤ 40 °C |
| 70 | Still almost quiet, a bit more air | Warm (CPU ~68 °C or HDD ~43 °C) |
| 90 | Audible but not intrusive | Hot, not in danger (CPU ~75 °C or HDD ~46 °C) |
| 110 | Audible; short periods only | Start of danger (CPU ~80 °C or HDD ~50 °C) |
| 124 | Hardware ceiling | Emergency (CPU ~85 °C or HDD ~55 °C) |

The service takes the **higher** of the two PWM values, with 2 °C hysteresis on the way down. It never writes above 124.

Wiring is an **L**, not a straight 1×3:

```text
Top:     11   9 PWM   7  …
Bottom:  12  10 12V   8 GND  6 5V …
```

Red → **10**, black → **8**, blue → **9** (above 12V).

Manual sweep (stop the service first):

```text
sudo systemctl stop core-fan
sudo /usr/local/sbin/core-fan-control --test
sudo systemctl start core-fan
```

## Fake-temp integration test

Does not heat the hardware. Stop the service, then `--once` with Celsius fakes (or millidegC via `CORE_FAN_CPU_MC` / `CORE_FAN_HDD_MC`). The fan will actually change speed.

```text
sudo systemctl stop core-fan
sudo /usr/local/sbin/core-fan-control --once --fake-cpu 35 --fake-hdd 27   # pwm=50
sudo /usr/local/sbin/core-fan-control --once --fake-cpu 68 --fake-hdd 40   # pwm=70
sudo /usr/local/sbin/core-fan-control --once --fake-cpu 75 --fake-hdd 27   # pwm=90
sudo /usr/local/sbin/core-fan-control --once --fake-cpu 35 --fake-hdd 50   # pwm=110 (HDD wins)
sudo /usr/local/sbin/core-fan-control --once --fake-cpu 85 --fake-hdd 40   # pwm=124
sudo systemctl start core-fan
```

Log lines include `(fake)` on the injected sensor. Omit a flag to use the real sensor for that side.

## If it fails

| Symptom | What to do |
|---|---|
| Full speed | PWM not on pin 9, or a value > 124. Confirm the L. `--test` should change speed at 50/70/90/110/124 |
| Service active, `hdd=0C` | IronWolf temp was not read; `lsblk -d -o NAME,TRAN,MODEL` and `smartctl -A /dev/sdX` |
| Fan never starts | PWM on pin 9. `pwm=50` is the quiet floor; `0` is off |
| Kernel and this service fight | `pwm1_enable` must be `1` (manual). The control loop writes that each tick |
