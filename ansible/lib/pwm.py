"""PWM scale: same step count on every source, duty is the highest demand.

Installed as /usr/local/sbin/site-pwm. SET writes /etc/site/pwm.json.
"""
from __future__ import annotations

import glob
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

INTERVAL_S = 15
HYSTERESIS_C = 2.0
CONFIG_PATH = Path("/etc/site/pwm.json")


def pwm_for_temp(temp_c: float, ceilings: list[float], steps: list[float]) -> int:
    """Map one temperature through ceiling:step pairs.

    At or below the first ceiling, the first step. Between ceilings, linear.
    Above the last ceiling, the last step.
    """
    t = float(temp_c)
    points = [float(c) for c in ceilings]
    duties = [int(s) for s in steps]
    if t <= points[0]:
        return duties[0]
    for i in range(len(points) - 1):
        lo_t, hi_t = points[i], points[i + 1]
        lo_p, hi_p = duties[i], duties[i + 1]
        if t <= hi_t:
            if hi_t == lo_t:
                return hi_p
            return int(lo_p + (hi_p - lo_p) * (t - lo_t) / (hi_t - lo_t))
    return duties[-1]


def source_curves(scale: dict[str, Any]) -> list[tuple[str, list[float]]]:
    """(label, ceilings) for cpu, each disk, and each gpu."""
    sources = scale.get("sources") or {}
    out: list[tuple[str, list[float]]] = []
    cpu = sources.get("cpu")
    if isinstance(cpu, list) and cpu:
        out.append(("cpu", [float(x) for x in cpu]))
    for kind in ("disks", "gpus"):
        for entry in sources.get(kind) or []:
            if not isinstance(entry, dict) or len(entry) != 1:
                continue
            ident, ceilings = next(iter(entry.items()))
            if isinstance(ceilings, list):
                out.append((f"{kind}.{ident}", [float(x) for x in ceilings]))
    return out


def target_pwm(temps: dict[str, float], scale: dict[str, Any]) -> int:
    """Highest step any reporting source demands, clamped to min/max."""
    steps = [int(s) for s in scale["steps"]]
    demands = []
    for label, ceilings in source_curves(scale):
        if label not in temps:
            continue
        demands.append(pwm_for_temp(temps[label], ceilings, steps))
    lo = int(scale.get("min", 0))
    hi = int(scale.get("max", max(steps) if steps else 0))
    if not demands:
        return lo
    return max(lo, min(hi, max(demands)))


def hold_pwm(new: int, last: int | None, temps: dict[str, float], scale: dict[str, Any]) -> int:
    """Keep the higher duty until every source has fallen hysteresis degrees."""
    if last is None or new >= last:
        return new
    bumped = {k: v + HYSTERESIS_C for k, v in temps.items()}
    if target_pwm(bumped, scale) >= last:
        return last
    return new


def _nondecreasing(nums: list[Any]) -> bool:
    vals = [float(n) for n in nums]
    return all(a <= b for a, b in zip(vals, vals[1:]))


def _host_ids(host: dict[str, Any]) -> tuple[set[str], set[str]]:
    disks = {
        str(d.get("id"))
        for d in ((host.get("resources") or {}).get("disks") or [])
        if isinstance(d, dict) and d.get("id")
    }
    gpus = {
        str(g.get("id"))
        for g in ((host.get("resources") or {}).get("gpu") or [])
        if isinstance(g, dict) and g.get("id")
    }
    return disks, gpus


def validate_pwm(desired: dict[str, Any]) -> list[str]:
    """Each source's temperature ceilings match steps. Disk and GPU ids exist on the host."""
    from .topology import hosts

    errors: list[str] = []
    for host in hosts(desired):
        name = host.get("name") or "host"
        pwm = (host.get("resources") or {}).get("pwm") or {}
        if not isinstance(pwm, dict):
            continue
        enabled = pwm.get("enabled") is True
        scale = pwm.get("scale")
        if enabled and not pwm.get("path"):
            errors.append(f"host {name} pwm.enabled requires path")
        if enabled and not isinstance(scale, dict):
            errors.append(f"host {name} pwm.enabled requires a scale map")
        if not isinstance(scale, dict):
            continue
        steps = scale.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"host {name} pwm scale steps must be a non-empty list")
            continue
        n = len(steps)
        if not _nondecreasing(steps):
            errors.append(f"host {name} pwm scale steps must be non-decreasing")
        lo = scale.get("min")
        hi = scale.get("max")
        if lo is not None and hi is not None and float(lo) > float(hi):
            errors.append(f"host {name} pwm scale min is above max")
        for step in steps:
            if lo is not None and float(step) < float(lo):
                errors.append(f"host {name} pwm scale step {step} is below min")
            if hi is not None and float(step) > float(hi):
                errors.append(f"host {name} pwm scale step {step} is above max")
        sources = scale.get("sources") or {}
        if not isinstance(sources, dict) or not sources:
            errors.append(f"host {name} pwm scale requires sources")
            continue
        disk_ids, gpu_ids = _host_ids(host)
        cpu = sources.get("cpu")
        if cpu is not None:
            if not isinstance(cpu, list) or len(cpu) != n:
                errors.append(f"host {name} pwm scale cpu has {len(cpu) if isinstance(cpu, list) else 0} ceilings, steps has {n}")
            elif not _nondecreasing(cpu):
                errors.append(f"host {name} pwm scale cpu ceilings must be non-decreasing")
        for kind, known in (("disks", disk_ids), ("gpus", gpu_ids)):
            entries = sources.get(kind)
            if entries is None:
                continue
            if not isinstance(entries, list):
                errors.append(f"host {name} pwm scale {kind} must be a list")
                continue
            for entry in entries:
                if not isinstance(entry, dict) or len(entry) != 1:
                    errors.append(f"host {name} pwm scale {kind} entries must map one id to a temperature list")
                    continue
                ident, ceilings = next(iter(entry.items()))
                ident = str(ident)
                if known and ident not in known:
                    errors.append(f"host {name} pwm scale {kind}.{ident} is not a {kind[:-1]} id on this host")
                if not isinstance(ceilings, list) or len(ceilings) != n:
                    got = len(ceilings) if isinstance(ceilings, list) else 0
                    errors.append(f"host {name} pwm scale {kind}.{ident} has {got} ceilings, steps has {n}")
                elif not _nondecreasing(ceilings):
                    errors.append(f"host {name} pwm scale {kind}.{ident} ceilings must be non-decreasing")
        if not any(k in sources for k in ("cpu", "disks", "gpus")):
            errors.append(f"host {name} pwm scale sources need cpu, disks, or gpus")
    return errors


def _read_mc(path: Path) -> float | None:
    try:
        raw = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if raw <= 0:
        return None
    return raw / 1000.0


def cpu_temp_c() -> float | None:
    root = Path("/sys/class/thermal")
    if not root.is_dir():
        return None
    temps = [c for z in root.glob("thermal_zone*/temp") if (c := _read_mc(z)) is not None]
    return max(temps) if temps else None


def disk_temp_c(disk_id: str) -> float | None:
    block = Path("/sys/block") / disk_id
    temps = [c for p in block.glob("device/hwmon/hwmon*/temp*_input") if (c := _read_mc(p)) is not None]
    if temps:
        return max(temps)
    if not shutil.which("smartctl"):
        return None
    try:
        raw = subprocess.check_output(
            ["smartctl", "-A", "-n", "never", f"/dev/{disk_id}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    for line in raw.splitlines():
        if "Current Drive Temperature" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                return float(parts[-1])
        bits = line.split()
        if len(bits) >= 10 and bits[1] in ("Temperature_Celsius", "Airflow_Temperature_Cel") and bits[9].isdigit():
            return float(bits[9])
    return None


def _nvidia_smi() -> str | None:
    found = shutil.which("nvidia-smi")
    if found and "/mnt/" not in found:
        return found
    for pat in ("/usr/bin/nvidia-smi", "/usr/lib/*/nvidia-smi", "/usr/lib/*/*/nvidia-smi"):
        for hit in glob.glob(pat):
            if "/mnt/" not in hit:
                return hit
    return None


def gpu_temp_c(gpu_id: str) -> float | None:
    binary = _nvidia_smi()
    if not binary:
        return None
    idx = str(gpu_id)
    if idx.startswith("gpu") and idx[3:].isdigit():
        idx = idx[3:]
    try:
        raw = subprocess.check_output(
            [binary, "-i", idx, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    try:
        return float(raw.splitlines()[0])
    except (ValueError, IndexError):
        return None


def read_temps(scale: dict[str, Any]) -> dict[str, float]:
    temps: dict[str, float] = {}
    sources = scale.get("sources") or {}
    if sources.get("cpu"):
        cpu = cpu_temp_c()
        if cpu is not None:
            temps["cpu"] = cpu
    for entry in sources.get("disks") or []:
        if isinstance(entry, dict) and len(entry) == 1:
            ident = str(next(iter(entry)))
            temp = disk_temp_c(ident)
            if temp is not None:
                temps[f"disks.{ident}"] = temp
    for entry in sources.get("gpus") or []:
        if isinstance(entry, dict) and len(entry) == 1:
            ident = str(next(iter(entry)))
            temp = gpu_temp_c(ident)
            if temp is not None:
                temps[f"gpus.{ident}"] = temp
    return temps


def apply_duty(path: Path, duty: int) -> None:
    enable = path.with_name(path.name + "_enable")
    if enable.is_file():
        enable.write_text("1\n", encoding="utf-8")
    path.write_text(f"{int(duty)}\n", encoding="utf-8")


def main() -> int:
    if not CONFIG_PATH.is_file():
        print(f"site-pwm: missing {CONFIG_PATH}", flush=True)
        return 1
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    path = Path(str(cfg.get("path") or ""))
    scale = cfg.get("scale") or {}
    last: int | None = None
    while True:
        if not path.is_file():
            print(f"site-pwm: {path} is not present", flush=True)
            time.sleep(INTERVAL_S)
            continue
        temps = read_temps(scale)
        duty = hold_pwm(target_pwm(temps, scale), last, temps, scale)
        if duty != last:
            try:
                apply_duty(path, duty)
            except OSError as exc:
                print(f"site-pwm: write {path} failed: {exc}", flush=True)
            else:
                parts = " ".join(f"{k}={v:.0f}C" for k, v in sorted(temps.items()))
                print(f"site-pwm: {parts} pwm={duty}", flush=True)
            last = duty
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
