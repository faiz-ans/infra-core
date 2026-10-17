#!/usr/bin/env python3
"""Power Backrest, Mantle restic-rest, and the Surface D: disk together.

This lives under windows/ because restic-rest runs in WSL2 and parks a drive
on the Windows host. GET/SET does not install it. Caddy already
proxies https://backup.home.lan to 127.0.0.1:9898. This process binds that
address and publishes Backrest on 127.0.0.1:19898 instead, via a Quadlet
drop-in under the loadmaster user. The Homepage widget keeps using the LAN
publish and does not count as activity.

The daily backup is 00:30 America/Los_Angeles (five minutes of lead time).
Sunday prune is 01:00. Both come from Backrest's config once it is up; the
seed schedule is the fallback. The seed writes that schedule only when
config.json is created. An existing Backrest config keeps its own crons
until they are changed in the UI. A browser request wakes the same three
parts. They turn off again after BACKUP_IDLE_MINUTES with no browser traffic
and no Backrest operation still running. A running operation finishes first,
and the idle period starts at that finish. SIGUSR1 ends that idle period
immediately so the next pass stops the stack. It does not cancel a
scheduled backup window.

On Sunday, after that window, Backrest and restic-rest stop and the D: disk
stays on for a SMART self-test. A short test runs every Sunday. The first
Sunday of the month runs a long test instead. The same test is started on
Core's IronWolf and is not waited on. D: is parked when its own test ends.

Before that park, and before a weekday park, one Scrutiny collect runs on
Surface. The drive is still enabled, so the collect posts both the Restic
disk and the internal SSD. The collector task has no schedule of its own.

SSH to Mantle uses a dedicated key whose server side is backup-remote. That
script accepts only restic-rest, D: on/off/status, smart short/long/status,
and collect / collect status.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import Message
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

log = logging.getLogger("backup-controller")

ZONE = ZoneInfo(os.environ.get("BACKUP_TZ", "America/Los_Angeles"))
SITE_HOST = os.environ.get("BACKUP_SITE_HOST", "backup.home.lan").lower()
IDLE = timedelta(minutes=int(os.environ.get("BACKUP_IDLE_MINUTES", "15")))
LEAD = timedelta(minutes=int(os.environ.get("BACKUP_LEAD_MINUTES", "5")))
ACL_LEAD = timedelta(seconds=int(os.environ.get("BACKUP_ACL_LEAD_SECONDS", "45")))
ACL_REFRESH = Path(os.environ.get("BACKUP_ACL_REFRESH", "/usr/local/sbin/site-backup-acl"))
GRACE = timedelta(minutes=int(os.environ.get("BACKUP_START_GRACE_MINUTES", "20")))
SKEW = timedelta(minutes=10)
LISTEN_HOST = os.environ.get("BACKUP_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("BACKUP_LISTEN_PORT", "9898"))
UPSTREAM_PORT = int(os.environ.get("BACKUP_UPSTREAM_PORT", "19898"))
MANTLE = os.environ.get("BACKUP_MANTLE", "pilot@192.168.1.111")
MANTLE_HOST = MANTLE.split("@", 1)[-1]
RESTIC_TCP = int(os.environ.get("BACKUP_RESTIC_PORT", "8000"))
SSH_KEY = Path(os.environ.get("BACKUP_SSH_KEY", str(Path.home() / ".ssh" / "backup_mantle")))
SSH_KNOWN = Path(os.environ.get("BACKUP_SSH_KNOWN", str(Path.home() / ".ssh" / "backup_mantle_known_hosts")))
QUADLET = Path(
    os.environ.get(
        "BACKUP_QUADLET",
        str(Path.home() / ".config" / "containers" / "systemd" / "backrest" / "backrest.container"),
    )
)
STATE_PATH = Path(
    os.environ.get(
        "BACKUP_STATE",
        str(Path.home() / ".local" / "state" / "backup-controller" / "state.json"),
    )
)

ALLOWED = (
    "restic-rest start",
    "restic-rest stop",
    "restic-rest status",
    "disk on",
    "disk off",
    "disk status",
    "smart short",
    "smart long",
    "smart status",
    "collect",
    "collect status",
)
LOOPBACK_PUBLISH = f"127.0.0.1:{LISTEN_PORT}:9898"
UPSTREAM_PUBLISH = f"127.0.0.1:{UPSTREAM_PORT}:9898"
RUNNING = {1, 2, "STATUS_PENDING", "STATUS_INPROGRESS"}
TERMINAL = {
    3,
    4,
    5,
    6,
    7,
    "STATUS_SUCCESS",
    "STATUS_WARNING",
    "STATUS_ERROR",
    "STATUS_SYSTEM_CANCELLED",
    "STATUS_USER_CANCELLED",
}
KIND_FIELDS = {
    "backup": ("operationBackup", "operation_backup"),
    "prune": ("operationPrune", "operation_prune"),
    "check": ("operationCheck", "operation_check"),
    "forget": ("operationForget", "operation_forget"),
}
DEFAULT_JOBS = (
    ("backup", "site-data", "30 0 * * *"),
    ("prune", "site", "0 1 * * 0"),
)
SMART_SCRIPT = Path(os.environ.get("BACKUP_SMART", "/usr/local/sbin/backup-smart"))
SMART_LIMIT = timedelta(hours=int(os.environ.get("BACKUP_SMART_LIMIT_HOURS", "18")))
COLLECT_LIMIT = timedelta(minutes=int(os.environ.get("BACKUP_COLLECT_MINUTES", "15")))
HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


@dataclass(frozen=True)
class Job:
    kind: str
    ident: str
    cron: str


class Busy(RuntimeError):
    pass


def pick(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj:
            return obj[key]
    return None


def field_match(expr: str, value: int, low: int, high: int) -> bool:
    for part in expr.split(","):
        step = 1
        if "/" in part:
            part, raw = part.split("/", 1)
            step = int(raw)
        if step < 1:
            return False
        if part in ("", "*"):
            start, end = low, high
        elif "-" in part:
            left, right = part.split("-", 1)
            start, end = int(left), int(right)
        else:
            start = end = int(part)
        if start <= value <= end and (value - start) % step == 0:
            return True
    return False


def dow_match(expr: str, sunday0: int) -> bool:
    if field_match(expr, sunday0, 0, 7):
        return True
    return sunday0 == 0 and field_match(expr, 7, 0, 7)


def acl_due(now: datetime, jobs: list[Job]) -> bool:
    """A job fires within ACL_LEAD. The read-access repair belongs here.

    A mode 0600 file or 0700 directory clears the ACL mask. The 00:00 sweep
    resets the tree; this repair catches anything created that way after it.
    """
    for job in jobs:
        minute = now.replace(second=0, microsecond=0)
        for step in (0, 1):
            when = minute + timedelta(minutes=step)
            if not cron_match(job.cron, when):
                continue
            remaining = when - now
            if timedelta(0) < remaining <= ACL_LEAD:
                return True
    return False


def cron_match(expr: str, when: datetime) -> bool:
    minute, hour, dom, month, dow = expr.split()
    if not field_match(minute, when.minute, 0, 59):
        return False
    if not field_match(hour, when.hour, 0, 23):
        return False
    if not field_match(month, when.month, 1, 12):
        return False
    dom_ok = field_match(dom, when.day, 1, 31)
    dow_ok = dow_match(dow, (when.weekday() + 1) % 7)
    if dom != "*" and dow != "*":
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def fire_on(cron: str, day: date, zone: ZoneInfo) -> datetime | None:
    found: list[datetime] = []
    for hour in range(24):
        for minute in range(60):
            when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
            if cron_match(cron, when):
                found.append(when)
    return min(found) if found else None


def cron_of(schedule: Any) -> str | None:
    if not isinstance(schedule, dict) or schedule.get("disabled") is True:
        return None
    cron = schedule.get("cron")
    if isinstance(cron, str) and cron.strip():
        return " ".join(cron.split())
    return None


def schedules_from_config(config: dict[str, Any]) -> list[Job]:
    jobs: list[Job] = []
    for plan in config.get("plans") or []:
        if not isinstance(plan, dict):
            continue
        cron = cron_of(plan.get("schedule"))
        if cron and plan.get("id"):
            jobs.append(Job("backup", str(plan["id"]), cron))
    for repo in config.get("repos") or []:
        if not isinstance(repo, dict) or not repo.get("id"):
            continue
        ident = str(repo["id"])
        for kind, key in (("prune", "prunePolicy"), ("check", "checkPolicy"), ("forget", "forgetPolicy")):
            policy = repo.get(key) or repo.get(key[0].lower() + key[1:])
            cron = cron_of((policy or {}).get("schedule") if isinstance(policy, dict) else None)
            if cron:
                jobs.append(Job(kind, ident, cron))
    return jobs


def default_jobs() -> list[Job]:
    return [Job(kind, ident, cron) for kind, ident, cron in DEFAULT_JOBS]


def jobs_today(jobs: list[Job], day: date, zone: ZoneInfo) -> list[tuple[Job, datetime]]:
    due: list[tuple[Job, datetime]] = []
    for job in jobs:
        when = fire_on(job.cron, day, zone)
        if when is not None:
            due.append((job, when))
    due.sort(key=lambda item: item[1])
    return due


def smart_mode(day: date) -> str | None:
    """short every Sunday, long on the first Sunday of the month."""
    if day.weekday() != 6:
        return None
    if day.day <= 7:
        return "long"
    return "short"


def surface_progress(seen_running: bool, token: str) -> tuple[bool, str]:
    """Return the updated seen-running flag and wait, done, or error.

    done before the task has reported running is the previous test's token.
    """
    word = (token or "").strip().split()[0] if token else "idle"
    if word == "running":
        return True, "wait"
    if word == "error":
        return seen_running, "error"
    if word == "done" and seen_running:
        return True, "done"
    return seen_running, "wait"


def window_deadline(jobs: list[Job], day: date, zone: ZoneInfo) -> datetime | None:
    due = jobs_today(jobs, day, zone)
    if not due:
        return None
    return due[-1][1] + GRACE


def should_open(now: datetime, jobs: list[Job], completed: date | None, zone: ZoneInfo) -> bool:
    if completed == now.date():
        return False
    due = jobs_today(jobs, now.date(), zone)
    if not due:
        return False
    start = due[0][1] - LEAD
    end = due[-1][1] + GRACE
    return start <= now <= end


def op_kind(op: dict[str, Any]) -> str:
    for kind, fields in KIND_FIELDS.items():
        for field in fields:
            if op.get(field) is not None and field in op:
                return kind
    return "other"


def op_ident(op: dict[str, Any], kind: str) -> str:
    if kind == "backup":
        return str(pick(op, "planId", "plan_id") or "")
    return str(pick(op, "repoId", "repo_id") or "")


def op_status(op: dict[str, Any]) -> Any:
    return pick(op, "status")


def is_running(op: dict[str, Any], now_ms: int | None = None) -> bool:
    # A missing status is the proto default, STATUS_UNKNOWN, not a live job.
    # STATUS_PENDING with a future start is the next scheduled run, which
    # Backrest inserts as soon as the previous one finishes. It is not work
    # in progress, and it must not hold the disk open.
    status = op_status(op)
    if status not in RUNNING:
        return False
    if status not in (1, "STATUS_PENDING"):
        return True
    started = start_ms(op)
    if started is None:
        return True
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    return started <= now_ms + 60_000


def is_terminal(op: dict[str, Any]) -> bool:
    return op_status(op) in TERMINAL


def start_ms(op: dict[str, Any]) -> int | None:
    raw = pick(op, "unixTimeStartMs", "unix_time_start_ms")
    if raw is None or raw == "":
        return None
    return int(raw)


def any_running(ops: list[dict[str, Any]]) -> bool:
    return any(is_running(op) for op in ops)


def job_satisfied(job: Job, ops: list[dict[str, Any]], window_start: datetime) -> bool:
    floor = int(window_start.timestamp() * 1000)
    for op in ops:
        if op_kind(op) != job.kind or op_ident(op, job.kind) != job.ident:
            continue
        started = start_ms(op)
        if started is None or started < floor:
            continue
        if is_terminal(op):
            return True
    return False


def window_status(
    now: datetime,
    jobs: list[Job],
    ops: list[dict[str, Any]],
    window_start: datetime,
    zone: ZoneInfo,
) -> str:
    """wait, done, or missed. missed means every remaining job is past its grace."""
    if any_running(ops):
        return "wait"
    due = jobs_today(jobs, window_start.astimezone(zone).date(), zone)
    pending = [(job, when) for job, when in due if not job_satisfied(job, ops, window_start)]
    if not pending:
        return "done"
    if any(now < when + GRACE for _job, when in pending):
        return "wait"
    return "missed"


class Hold:
    def __init__(self) -> None:
        self.interactive = False
        self.cron = False
        self.smart = False
        self.last_activity: datetime | None = None
        self.job_running = False
        self.job_idle_since: datetime | None = None

    def browser(self, now: datetime) -> None:
        self.interactive = True
        self.last_activity = now

    def set_jobs(self, running: bool, now: datetime) -> None:
        if running:
            self.job_running = True
            self.job_idle_since = None
            return
        if self.job_running:
            self.job_idle_since = now
        self.job_running = False

    def release_interactive(self, now: datetime) -> None:
        if not self.interactive or self.job_running:
            return
        anchors = [item for item in (self.last_activity, self.job_idle_since) if item is not None]
        if not anchors:
            return
        if now - max(anchors) >= IDLE:
            self.interactive = False

    def expire(self) -> None:
        self.interactive = False
        self.last_activity = None
        self.job_idle_since = None

    def wants_power(self) -> bool:
        return self.interactive or self.cron


def request_wakes(headers: Message | dict[str, str]) -> bool:
    getter = headers.get
    for key in ("X-Forwarded-Host", "Host"):
        raw = getter(key)
        if not raw:
            continue
        host = str(raw).split(",")[0].strip().split(":")[0].lower()
        if host == SITE_HOST:
            return True
    return False


def desired_publish(container_text: str) -> list[str]:
    found = re.findall(r"(?m)^PublishPort=(.+)$", container_text)
    kept: list[str] = []
    for item in found:
        item = item.strip()
        if item in (LOOPBACK_PUBLISH, UPSTREAM_PUBLISH):
            continue
        if item not in kept:
            kept.append(item)
    kept.append(UPSTREAM_PUBLISH)
    return kept


def dropin_text(ports: list[str]) -> str:
    lines = ["[Container]", "PublishPort="]
    lines.extend(f"PublishPort={port}" for port in ports)
    return "\n".join(lines) + "\n"


def host_of(raw: str) -> str:
    return raw.split(",")[0].strip().split(":")[0].lower()


class Stack:
    """Start disk, then restic-rest, then Backrest. Stop in reverse."""

    def __init__(self, remote: Any) -> None:
        self.remote = remote

    def power_on(self) -> None:
        try:
            self.remote.disk("on")
            self.remote.wait_disk("ready")
            self.remote.restic("start")
            self.remote.wait_restic()
            self.remote.backrest("start")
            self.remote.wait_api()
        except Exception:
            log.exception("power on failed; turning the stack back off")
            try:
                self.power_off(force=True)
            except Exception:
                log.exception("rollback failed")
            raise

    def power_off(
        self,
        force: bool = False,
        leave_disk: bool = False,
        keep: Callable[[], bool] | None = None,
    ) -> None:
        # A page opened while this was already stopping has a live idle timer.
        # Do not park the disk out from under it. Check again before the park:
        # stopping Backrest is slow enough for the visit to arrive in between.
        if keep and keep():
            return
        if not force and self.remote.jobs_running():
            raise Busy("a Backrest operation is still running")
        if keep and keep():
            return
        self.remote.backrest("stop")
        if keep and keep():
            return
        self.remote.restic("stop")
        if leave_disk or (keep and keep()):
            return
        try:
            self.remote.collect_and_wait()
        except Exception:
            log.exception("surface collect failed; parking the disk")
        if keep and keep():
            return
        self.remote.disk("off")
        self.remote.wait_disk("off")


class Gate:
    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.phase = "off"
        self.error: BaseException | None = None

    def ensure_on(self, start: Callable[[], None]) -> None:
        with self.cv:
            while self.phase == "stopping":
                self.cv.wait()
            if self.phase == "on":
                return
            if self.phase == "starting":
                while self.phase == "starting":
                    self.cv.wait()
                if self.error is not None:
                    raise self.error
                if self.phase != "on":
                    raise RuntimeError("backup stack did not start")
                return
            self.phase = "starting"
            self.error = None
        try:
            start()
        except Exception as exc:
            with self.cv:
                self.phase = "off"
                self.error = exc
                self.cv.notify_all()
            raise
        with self.cv:
            self.phase = "on"
            self.error = None
            self.cv.notify_all()

    def ensure_off(self, stop: Callable[[], None]) -> None:
        with self.cv:
            if self.phase != "on":
                return
            self.phase = "stopping"
        try:
            stop()
        except Exception:
            # power_off stops Backrest before it waits for the disk. Leaving the
            # gate "on" made the next visit proxy to a port nothing was listening on.
            with self.cv:
                self.phase = "on" if backrest_active() else "off"
                self.cv.notify_all()
            raise
        with self.cv:
            self.phase = "off"
            self.cv.notify_all()


class Remote:
    def disk(self, action: str) -> str:
        return self._ssh(f"disk {action}")

    def smart(self, action: str) -> str:
        return self._ssh(f"smart {action}")

    def collect_and_wait(self) -> None:
        # backup-remote writes "running" before the task starts, so a done or
        # error token from this point belongs to this run.
        log.info("collecting Surface SMART before parking the disk")
        self._ssh("collect")
        deadline = time.monotonic() + COLLECT_LIMIT.total_seconds()
        last = ""
        while time.monotonic() < deadline:
            last = self._ssh("collect status").strip().splitlines()[-1].strip()
            word = last.split()[0] if last else "idle"
            if word == "done":
                log.info("surface collect finished")
                return
            if word == "error":
                raise RuntimeError("surface collect failed")
            time.sleep(2)
        raise TimeoutError(f"surface collect stayed {last or 'unknown'}")

    def restic(self, action: str) -> str:
        return self._ssh(f"restic-rest {action}")

    def wait_disk(self, want: str) -> None:
        deadline = time.monotonic() + 120
        last = ""
        while time.monotonic() < deadline:
            last = self.disk("status").strip().splitlines()[-1].strip()
            if last == want:
                return
            if last.startswith("error:"):
                raise RuntimeError(last)
            time.sleep(2)
        raise TimeoutError(f"D: stayed {last or 'unknown'}, wanted {want}")

    def wait_restic(self) -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.restic("status").strip().splitlines()[-1].strip() == "active" and tcp_open(MANTLE_HOST, RESTIC_TCP):
                return
            time.sleep(2)
        raise TimeoutError("restic-rest did not accept connections")

    def backrest(self, action: str) -> None:
        if action == "start":
            heal_dropin()
            systemctl("reset-failed", check=False)
            systemctl("start")
            return
        systemctl("stop")

    def wait_api(self) -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                api_post(UPSTREAM_PORT, "GetConfig", {})
                return
            except Exception:
                time.sleep(2)
        if backrest_active() and not tcp_open(LISTEN_HOST, UPSTREAM_PORT):
            raise TimeoutError(f"Backrest did not open {UPSTREAM_PORT}; the quadlet drop-in did not take effect")
        raise TimeoutError("Backrest API did not answer")

    def jobs_running(self) -> bool:
        if not backrest_active():
            return False
        try:
            return any_running(read_operations())
        except Exception as exc:
            log.warning("Backrest API did not answer (%s)", exc)
            return False

    def leftovers(self) -> bool:
        if backrest_active():
            return True
        restic = self.restic("status").strip().splitlines()[-1].strip()
        if restic == "active":
            return True
        disk = self.disk("status").strip().splitlines()[-1].strip()
        return disk != "off"

    def _ssh(self, command: str) -> str:
        if command not in ALLOWED:
            raise ValueError(f"refusing SSH command {command!r}")
        run = subprocess.run(
            [
                "ssh",
                "-i",
                str(SSH_KEY),
                "-o",
                "BatchMode=yes",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                f"UserKnownHostsFile={SSH_KNOWN}",
                "-o",
                "ConnectTimeout=10",
                MANTLE,
                command,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if run.returncode != 0 and not command.endswith(" status"):
            detail = (run.stderr or run.stdout or "").strip()
            raise RuntimeError(f"{command} failed: {detail}")
        return run.stdout


def tcp_open(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), 3):
            return True
    except OSError:
        return False


def systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    run = subprocess.run(
        ["systemctl", "--user", *args, "backrest.service"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30 if args != ("stop",) else 60,
    )
    if check and run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip()
        raise RuntimeError(f"systemctl {' '.join(args)} backrest failed: {detail}")
    return run


def backrest_active() -> bool:
    run = systemctl("is-active", check=False)
    return run.stdout.strip() == "active"


def heal_dropin() -> None:
    if not QUADLET.is_file():
        raise RuntimeError(f"Backrest unit file is missing: {QUADLET}")
    text = dropin_text(desired_publish(QUADLET.read_text(encoding="utf-8")))
    path = QUADLET.parent / "backrest.container.d" / "10-listen.conf"
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    if current == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=30)
    log.info("Backrest loopback publish is %s", UPSTREAM_PUBLISH)


def api_post(port: int, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    conn = HTTPConnection(LISTEN_HOST, port, timeout=10)
    try:
        body = json.dumps(payload).encode()
        conn.request(
            "POST",
            f"/v1.Backrest/{method}",
            body=body,
            headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1"},
        )
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status != 200:
            snippet = raw.decode(errors="replace").strip().replace("\n", " ")[:180]
            raise RuntimeError(f"{method} on port {port} HTTP {resp.status} {snippet}".strip())
        data = json.loads(raw.decode() or "{}")
    finally:
        conn.close()
    if not isinstance(data, dict):
        raise RuntimeError(f"{method} returned {type(data).__name__}")
    return data


def read_operations() -> list[dict[str, Any]]:
    """Read recent operations from whichever port Backrest is actually publishing."""
    ports = [port for port in (UPSTREAM_PORT, LISTEN_PORT) if port_open(port)]
    if not ports:
        raise RuntimeError("Backrest API is not listening")
    errors: list[str] = []
    for port in ports:
        try:
            payload = api_post(port, "GetOperations", {"selector": {"lastN": 200}})
        except Exception as exc:
            errors.append(str(exc))
            continue
        ops = payload.get("operations") or []
        return [op for op in ops if isinstance(op, dict)]
    raise RuntimeError("; ".join(errors))


def load_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


def save_state(data: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def jobs_from_state(data: dict[str, Any]) -> list[Job]:
    raw = data.get("jobs")
    jobs: list[Job] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, list) and len(item) == 3:
                jobs.append(Job(str(item[0]), str(item[1]), str(item[2])))
    return jobs or default_jobs()


def parse_day(raw: Any) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_stamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=ZONE)
    return when


class Controller:
    def __init__(self, remote: Remote | None = None) -> None:
        self.remote = remote or Remote()
        self.stack = Stack(self.remote)
        self.gate = Gate()
        self.hold = Hold()
        self.lock = threading.Lock()
        state = load_state()
        self.jobs = jobs_from_state(state)
        self.completed = parse_day(state.get("completed_on"))
        self.window_start = parse_stamp(state.get("window_start"))
        smart = state.get("smart") if isinstance(state.get("smart"), dict) else {}
        self.smart_date = parse_day(smart.get("date"))
        self.smart_mode_name = smart.get("mode") if smart.get("mode") in ("short", "long") else None
        self.smart_started = bool(smart.get("started"))
        self.smart_seen = bool(smart.get("seen_running"))
        self.smart_finished = bool(smart.get("finished"))
        self.smart_started_at = parse_stamp(smart.get("started_at"))
        if (
            self.smart_date is not None
            and not self.smart_finished
            and self.smart_mode_name is not None
        ):
            self.hold.smart = True
        self.server: ThreadingHTTPServer | None = None
        self.last_reconcile = datetime.min.replace(tzinfo=ZONE)
        self.last_acl = 0.0

    def now(self) -> datetime:
        return datetime.now(ZONE)

    def persist(self) -> None:
        save_state(
            {
                "completed_on": self.completed.isoformat() if self.completed else "",
                "window_start": self.window_start.isoformat() if self.window_start else "",
                "jobs": [[job.kind, job.ident, job.cron] for job in self.jobs],
                "smart": {
                    "date": self.smart_date.isoformat() if self.smart_date else "",
                    "mode": self.smart_mode_name or "",
                    "started": self.smart_started,
                    "seen_running": self.smart_seen,
                    "finished": self.smart_finished,
                    "started_at": self.smart_started_at.isoformat() if self.smart_started_at else "",
                },
            }
        )

    def operations(self) -> list[dict[str, Any]]:
        return read_operations()

    def refresh_jobs(self) -> None:
        try:
            config = api_post(UPSTREAM_PORT, "GetConfig", {})
        except Exception:
            log.warning("using the saved Backrest schedule")
            return
        jobs = schedules_from_config(config)
        self.jobs = jobs
        log.info("schedule %s", ", ".join(f"{job.kind}:{job.ident} {job.cron}" for job in jobs) or "none")
        self.persist()

    def finish_window(self, status: str, now: datetime) -> None:
        if status == "missed":
            log.error("scheduled backup work did not start; turning the disk off")
        else:
            log.info("scheduled backup work finished")
        self.hold.cron = False
        if self.window_start is not None:
            self.completed = self.window_start.astimezone(ZONE).date()
        else:
            self.completed = now.date()
        self.window_start = None
        mode = smart_mode(self.completed) if status == "done" else None
        if mode and not (self.smart_finished and self.smart_date == self.completed):
            self.hold.smart = True
            self.smart_date = self.completed
            self.smart_mode_name = mode
            if not self.smart_started:
                self.smart_seen = False
                self.smart_finished = False
                self.smart_started_at = None
        self.persist()

    def refresh_read_access(self) -> None:
        """Restore read access on the mode-0600 backup paths. Returns when done.

        Call this only from the scheduler and from the Backup request. A walk
        of every source root takes long enough to time out the Backrest UI.
        """
        if not ACL_REFRESH.is_file():
            return
        result = subprocess.run(
            ["sudo", "-n", str(ACL_REFRESH), "repair"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            log.warning("backup read access was not refreshed (%s)", detail or result.returncode)

    def tick(self) -> None:
        try:
            heal_dropin()
        except Exception:
            log.exception("quadlet drop-in")
        now = self.now()
        with self.lock:
            started = self.window_start.astimezone(ZONE).date() if self.window_start is not None else None
            deadline = window_deadline(self.jobs, started, ZONE) if started is not None else None
            resume = (
                started == now.date()
                and self.completed != now.date()
                and deadline is not None
                and now <= deadline
            )
            if (
                self.window_start is not None
                and self.completed != now.date()
                and not resume
                and not should_open(now, self.jobs, self.completed, ZONE)
            ):
                # A failed wake earlier today must not keep turning the disk on all evening.
                self.finish_window("missed", now)
            if resume or should_open(now, self.jobs, self.completed, ZONE):
                self.hold.cron = True
                if self.window_start is None:
                    self.window_start = now - SKEW
                    self.persist()
        if self.hold.cron and self.gate.phase != "on":
            try:
                self.gate.ensure_on(self._on)
            except Exception:
                log.exception("scheduled wake failed")
                return
        if self.gate.phase == "on":
            if acl_due(now, self.jobs) and time.monotonic() - self.last_acl >= 30:
                self.last_acl = time.monotonic()
                self.refresh_read_access()
            if self.hold.wants_power() and not backrest_active():
                try:
                    self.remote.backrest("start")
                except Exception:
                    log.exception("Backrest restart failed")
            self._watch(now)
        elif self.gate.phase == "off" and not self.hold.smart and now - self.last_reconcile >= timedelta(seconds=30):
            self.last_reconcile = now
            self._reconcile_off()

    def _on(self) -> None:
        self.stack.power_on()
        with self.lock:
            if self.hold.interactive:
                self.hold.last_activity = self.now()
        self.refresh_jobs()

    def _watch(self, now: datetime) -> None:
        if not backrest_active():
            running = False
            ops = []
        else:
            try:
                ops = self.operations()
            except Exception as exc:
                log.warning("Backrest API did not answer (%s)", exc)
                running = False
                ops = []
            else:
                running = any_running(ops)
        with self.lock:
            self.hold.set_jobs(running, now)
            self.hold.release_interactive(now)
            if self.hold.cron and self.window_start is not None and not running:
                status = window_status(now, self.jobs, ops, self.window_start, ZONE)
                if status in ("done", "missed"):
                    self.finish_window(status, now)
            want = self.hold.wants_power()
            smart = self.hold.smart
        if not want:
            try:
                if smart:
                    if self.gate.phase == "on":
                        self.gate.ensure_off(lambda: self.stack.power_off(leave_disk=True, keep=self._held))
                    self._run_smart(now)
                else:
                    self.gate.ensure_off(lambda: self.stack.power_off(keep=self._held))
            except Busy:
                log.info("shutdown waited for a Backrest operation")
            except Exception:
                log.exception("shutdown failed")

    def expire_idle(self) -> None:
        with self.lock:
            self.hold.expire()
        log.info("idle timer expired")

    def _held(self) -> bool:
        with self.lock:
            return self.hold.wants_power() or self.hold.smart

    def _reconcile_off(self) -> None:
        # The disk may already be on from disk-on outside this process. Park it
        # only while no idle timer is running. A visit sets the timer and waits
        # out this stop, so the park must not land after that visit.
        if self._held():
            return
        with self.gate.cv:
            if self.gate.phase != "off":
                return
            self.gate.phase = "stopping"
            self.gate.cv.notify_all()
        busy = False
        try:
            if self._held():
                return
            if not self.remote.leftovers():
                return
            log.info("stack is up with nobody using it; turning it off")
            self.stack.power_off(keep=self._held)
        except Busy:
            # The operation may have started before this process. Count anything
            # from the beginning of the local day, not from this check.
            busy = True
            with self.lock:
                self.hold.cron = True
                start = datetime.combine(self.now().date(), datetime.min.time(), tzinfo=ZONE)
                if self.window_start is None or self.window_start > start:
                    self.window_start = start
                    self.persist()
        except Exception:
            log.exception("idle check failed")
        finally:
            with self.gate.cv:
                if self.gate.phase == "stopping":
                    self.gate.phase = "off"
                self.gate.cv.notify_all()
        if not busy:
            return
        try:
            self.gate.ensure_on(lambda: None)
        except Exception:
            log.exception("could not record the in-progress operation")

    def _ironwolf(self, mode: str) -> None:
        if mode not in ("short", "long"):
            return
        run = subprocess.run(
            ["sudo", "-n", str(SMART_SCRIPT), mode],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if run.returncode != 0:
            detail = (run.stderr or run.stdout or "").strip()
            log.error("IronWolf %s test did not start (%s)", mode, detail or run.returncode)
            return
        log.info("IronWolf %s test started", mode)

    def _park_surface(self) -> None:
        try:
            self.remote.collect_and_wait()
        except Exception:
            log.exception("surface collect failed; parking the disk")
        self.remote.disk("off")
        self.remote.wait_disk("off")
        self.hold.smart = False
        self.smart_finished = True
        self.persist()
        log.info("Restic disk parked")

    def _run_smart(self, now: datetime) -> None:
        mode = self.smart_mode_name or smart_mode(now.date())
        if mode not in ("short", "long"):
            self.hold.smart = False
            self.persist()
            return
        if self.smart_started_at is not None and now - self.smart_started_at > SMART_LIMIT:
            log.error("surface SMART exceeded %s; parking the disk", SMART_LIMIT)
            self._park_surface()
            return
        if not self.smart_started:
            try:
                self.remote.smart(mode)
            except Exception:
                log.exception("surface SMART did not start; parking the disk")
                try:
                    self._ironwolf(mode)
                except Exception:
                    log.exception("IronWolf SMART")
                self._park_surface()
                return
            try:
                self._ironwolf(mode)
            except Exception:
                log.exception("IronWolf SMART")
            self.smart_started = True
            self.smart_started_at = now
            self.persist()
        token = self.remote.smart("status").strip().splitlines()[-1].strip()
        seen, result = surface_progress(self.smart_seen, token)
        if seen != self.smart_seen:
            self.smart_seen = seen
            self.persist()
        if result == "wait":
            return
        if result == "error":
            log.error("surface SMART failed; parking the disk")
        else:
            log.info("surface %s SMART test finished", mode)
        self._park_surface()

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        if request_wakes(handler.headers):
            with self.lock:
                self.hold.browser(self.now())
            try:
                self.gate.ensure_on(self._on)
            except Exception as exc:
                handler.send_error(503, explain(exc))
                return
        elif self.gate.phase != "on":
            handler.send_error(503, "Backrest is off")
            return
        if handler.path.rstrip("/").endswith("/Backup"):
            self.refresh_read_access()
        proxy(handler, UPSTREAM_PORT)


def explain(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:200]


def proxy(handler: BaseHTTPRequestHandler, port: int) -> None:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if handler.headers.get("Transfer-Encoding"):
        handler.send_error(400, "chunked upload is not supported")
        return
    conn = HTTPConnection(LISTEN_HOST, port, timeout=10)
    try:
        conn.connect()
        if conn.sock is not None:
            conn.sock.settimeout(None)
        conn.putrequest(handler.command, handler.path, skip_host=True, skip_accept_encoding=True)
        for key, value in handler.headers.items():
            if key.lower() not in HOP:
                conn.putheader(key, value)
        conn.putheader("Content-Length", str(length))
        conn.endheaders()
        remaining = length
        while remaining:
            chunk = handler.rfile.read(min(65536, remaining))
            if not chunk:
                break
            conn.send(chunk)
            remaining -= len(chunk)
        resp = conn.getresponse()
        handler.send_response(resp.status, resp.reason)
        upstream_len = resp.getheader("Content-Length")
        for key, value in resp.headers.items():
            if key.lower() not in HOP:
                handler.send_header(key, value)
        handler.send_header("Connection", "close")
        if upstream_len is None:
            handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        if upstream_len is not None:
            left = int(upstream_len)
            while left:
                chunk = resp.read(min(65536, left))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                left -= len(chunk)
        else:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    handler.wfile.write(b"0\r\n\r\n")
                    break
                handler.wfile.write(f"{len(chunk):X}\r\n".encode())
                handler.wfile.write(chunk + b"\r\n")
        handler.wfile.flush()
    except Exception as exc:
        if not handler.wfile.closed:
            try:
                handler.send_error(502, explain(exc))
            except Exception:
                log.exception("proxy error")
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    controller: Controller

    def do_GET(self) -> None:  # noqa: N802
        self.controller.handle(self)

    do_POST = do_GET
    do_PUT = do_GET
    do_PATCH = do_GET
    do_DELETE = do_GET
    do_HEAD = do_GET
    do_OPTIONS = do_GET

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def port_open(port: int) -> bool:
    return tcp_open(LISTEN_HOST, port)


def prepare_listen(controller: Controller) -> bool:
    """Free 127.0.0.1:9898. Leave Backrest alone while an operation is running."""
    try:
        heal_dropin()
    except Exception:
        log.exception("quadlet drop-in")
    listen = port_open(LISTEN_PORT)
    if not listen:
        return True
    if backrest_active():
        try:
            ops = read_operations()
        except Exception as exc:
            log.warning("Backrest API on %s failed (%s); stopping it", LISTEN_PORT, exc)
            ops = []
        if any_running(ops):
            running = [op for op in ops if is_running(op)]
            log.info(
                "Backrest is on %s during %s operation(s); waiting to move it",
                LISTEN_PORT,
                len(running),
            )
            return False
        log.info("stopping Backrest so the controller can listen on %s", LISTEN_PORT)
        systemctl("stop", check=False)
        time.sleep(1)
        return not port_open(LISTEN_PORT)
    log.info("port %s is in use and Backrest is not the listener", LISTEN_PORT)
    return False


def serve(controller: Controller) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"controller": controller})
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="backup-http", daemon=True)
    thread.start()
    log.info("listening on %s:%s for %s", LISTEN_HOST, LISTEN_PORT, SITE_HOST)
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if shutil.which("ssh") is None:
        raise SystemExit("ssh is not installed")
    controller = Controller()
    stop = threading.Event()

    def quit_handler(signum: int, _frame: Any) -> None:
        log.info("signal %s", signum)
        stop.set()

    import signal

    def expire_handler(signum: int, _frame: Any) -> None:
        log.info("signal %s", signum)
        controller.expire_idle()

    signal.signal(signal.SIGTERM, quit_handler)
    signal.signal(signal.SIGINT, quit_handler)
    signal.signal(signal.SIGUSR1, expire_handler)
    while not stop.is_set():
        if controller.server is None and prepare_listen(controller):
            try:
                controller.server = serve(controller)
            except OSError:
                log.exception("bind %s:%s", LISTEN_HOST, LISTEN_PORT)
        try:
            controller.tick()
        except Exception:
            log.exception("tick")
        stop.wait(5)
    if controller.server is not None:
        controller.server.shutdown()


if __name__ == "__main__":
    main()
