#!/usr/bin/env python3
"""Decision tests for the personal backup controller. No SSH, no systemd."""

from __future__ import annotations

import json
import os
import subprocess
from unittest.mock import patch
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta
from email.message import Message
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("BACKUP_STATE", str(Path(tempfile.mkdtemp()) / "state.json"))
os.environ.setdefault("BACKUP_QUADLET", "/no/such/backrest.container")

import backup_controller as bc  # noqa: E402

ZONE = ZoneInfo("America/Los_Angeles")
ROOT = Path(__file__).resolve().parent


def at(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE)


class CronTests(unittest.TestCase):
    def test_daily_backup_and_sunday_prune(self) -> None:
        wednesday = date(2026, 10, 14)
        sunday = date(2026, 10, 18)
        self.assertEqual(wednesday.weekday(), 2)
        self.assertEqual(sunday.weekday(), 6)
        self.assertEqual(bc.fire_on("0 3 * * *", wednesday, ZONE), at(wednesday, 3, 0))
        jobs = [bc.Job("backup", "site-data", "0 3 * * *")]
        self.assertFalse(bc.acl_due(at(wednesday, 2, 56), jobs))
        self.assertTrue(bc.acl_due(at(wednesday, 2, 59).replace(second=20), jobs))
        self.assertFalse(bc.acl_due(at(wednesday, 3, 0), jobs))
        self.assertIsNone(bc.fire_on("30 3 * * 0", wednesday, ZONE))
        self.assertEqual(bc.fire_on("30 3 * * 0", sunday, ZONE), at(sunday, 3, 30))
        self.assertEqual(bc.fire_on("30 3 * * 7", sunday, ZONE), at(sunday, 3, 30))

    def test_window_opens_five_minutes_early(self) -> None:
        wednesday = date(2026, 10, 14)
        jobs = bc.default_jobs()
        self.assertFalse(bc.should_open(at(wednesday, 2, 54), jobs, None, ZONE))
        self.assertTrue(bc.should_open(at(wednesday, 2, 55), jobs, None, ZONE))
        self.assertTrue(bc.should_open(at(wednesday, 3, 20), jobs, None, ZONE))
        self.assertFalse(bc.should_open(at(wednesday, 3, 21), jobs, None, ZONE))
        self.assertFalse(bc.should_open(at(wednesday, 2, 55), jobs, wednesday, ZONE))
        self.assertGreater(at(wednesday, 23, 29), bc.window_deadline(jobs, wednesday, ZONE))
        sunday = date(2026, 10, 18)
        self.assertTrue(bc.should_open(at(sunday, 3, 40), jobs, None, ZONE))
        self.assertFalse(bc.should_open(at(sunday, 3, 51), jobs, None, ZONE))


def op(kind: str, status: str, start: datetime, plan: str = "", repo: str = "site") -> dict:
    body = {
        "status": status,
        "unixTimeStartMs": str(int(start.timestamp() * 1000)),
        "planId": plan,
        "repoId": repo,
    }
    field = {"backup": "operationBackup", "prune": "operationPrune", "forget": "operationForget"}[kind]
    body[field] = {}
    return body


class OperationTests(unittest.TestCase):
    def test_missing_status_is_not_a_running_job(self) -> None:
        self.assertFalse(bc.is_running({}))
        self.assertFalse(bc.is_running({"status": "STATUS_UNKNOWN"}))
        self.assertFalse(bc.is_running({"status": 0}))
        self.assertTrue(bc.is_running({"status": "STATUS_INPROGRESS"}))
        self.assertFalse(bc.any_running([{}]))


class WindowTests(unittest.TestCase):
    def test_weekday_backup_success_is_done(self) -> None:
        day = date(2026, 10, 14)
        start = at(day, 2, 45)
        ops = [op("backup", "STATUS_SUCCESS", at(day, 3, 0), plan="site-data")]
        self.assertEqual(bc.window_status(at(day, 4, 0), bc.default_jobs(), ops, start, ZONE), "done")

    def test_error_counts_as_completion(self) -> None:
        day = date(2026, 10, 14)
        start = at(day, 2, 45)
        ops = [op("backup", "STATUS_ERROR", at(day, 3, 1), plan="site-data")]
        self.assertEqual(bc.window_status(at(day, 3, 10), bc.default_jobs(), ops, start, ZONE), "done")

    def test_running_forget_holds_the_disk(self) -> None:
        day = date(2026, 10, 14)
        start = at(day, 2, 45)
        ops = [
            op("backup", "STATUS_SUCCESS", at(day, 3, 0), plan="site-data"),
            op("forget", "STATUS_INPROGRESS", at(day, 3, 20)),
        ]
        self.assertEqual(bc.window_status(at(day, 3, 21), bc.default_jobs(), ops, start, ZONE), "wait")

    def test_sunday_waits_for_prune(self) -> None:
        day = date(2026, 10, 18)
        start = at(day, 2, 45)
        ops = [op("backup", "STATUS_SUCCESS", at(day, 3, 0), plan="site-data")]
        self.assertEqual(bc.window_status(at(day, 3, 40), bc.default_jobs(), ops, start, ZONE), "wait")
        ops.append(op("prune", "STATUS_SUCCESS", at(day, 3, 31)))
        self.assertEqual(bc.window_status(at(day, 3, 45), bc.default_jobs(), ops, start, ZONE), "done")

    def test_later_sunday_job_keeps_an_early_miss_open(self) -> None:
        day = date(2026, 10, 18)
        start = at(day, 2, 45)
        self.assertEqual(bc.window_status(at(day, 3, 25), bc.default_jobs(), [], start, ZONE), "wait")
        self.assertEqual(bc.window_status(at(day, 3, 51), bc.default_jobs(), [], start, ZONE), "missed")

    def test_yesterday_does_not_satisfy_today(self) -> None:
        day = date(2026, 10, 14)
        start = at(day, 2, 45)
        ops = [op("backup", "STATUS_SUCCESS", at(date(2026, 10, 13), 3, 0), plan="site-data")]
        self.assertEqual(bc.window_status(at(day, 3, 10), bc.default_jobs(), ops, start, ZONE), "wait")


class HoldTests(unittest.TestCase):
    def test_idle_period(self) -> None:
        hold = bc.Hold()
        opened = at(date(2026, 10, 14), 12, 0)
        hold.browser(opened)
        hold.set_jobs(False, opened)
        hold.release_interactive(opened + timedelta(minutes=14))
        self.assertTrue(hold.interactive)
        hold.release_interactive(opened + bc.IDLE)
        self.assertFalse(hold.interactive)

    def test_job_then_full_idle_after_it_finishes(self) -> None:
        hold = bc.Hold()
        opened = at(date(2026, 10, 14), 12, 0)
        hold.browser(opened)
        hold.set_jobs(True, opened)
        finished = opened + timedelta(hours=1)
        hold.set_jobs(False, finished)
        hold.release_interactive(finished + timedelta(minutes=14))
        self.assertTrue(hold.interactive)
        hold.release_interactive(finished)
        self.assertTrue(hold.wants_power())
        hold.release_interactive(finished + bc.IDLE)
        self.assertFalse(hold.interactive)

    def test_click_after_the_job_restarts_the_idle_period(self) -> None:
        hold = bc.Hold()
        finished = at(date(2026, 10, 14), 13, 0)
        hold.browser(finished - timedelta(hours=1))
        hold.set_jobs(True, finished - timedelta(hours=1))
        hold.set_jobs(False, finished)
        click = finished + timedelta(minutes=10)
        hold.browser(click)
        hold.release_interactive(click + timedelta(minutes=14))
        self.assertTrue(hold.interactive)
        hold.release_interactive(click + bc.IDLE)
        self.assertFalse(hold.interactive)


class RequestTests(unittest.TestCase):
    def test_only_the_backup_site_wakes(self) -> None:
        def headers(host: str, forwarded: str = "") -> Message:
            msg = Message()
            msg["Host"] = host
            if forwarded:
                msg["X-Forwarded-Host"] = forwarded
            return msg

        self.assertTrue(bc.request_wakes(headers("backup.home.lan")))
        self.assertTrue(bc.request_wakes(headers("backup.home.lan:9898")))
        self.assertTrue(bc.request_wakes(headers("127.0.0.1:9898", "backup.home.lan")))
        self.assertFalse(bc.request_wakes(headers("169.254.1.2:9898")))
        self.assertFalse(bc.request_wakes(headers("backrest.home.lan")))
        self.assertFalse(bc.request_wakes(headers("192.168.1.110:9898")))


class ScheduleTests(unittest.TestCase):
    def test_seed_shape_and_disabled_prune(self) -> None:
        config = {
            "plans": [{"id": "site-data", "schedule": {"cron": "0 3 * * *", "clock": "CLOCK_LOCAL"}}],
            "repos": [
                {
                    "id": "site",
                    "prunePolicy": {"schedule": {"cron": "30 3 * * 0", "clock": "CLOCK_LOCAL"}},
                    "checkPolicy": {"schedule": {"disabled": True, "cron": "0 4 1 * *"}},
                }
            ],
        }
        jobs = bc.schedules_from_config(config)
        self.assertEqual([(job.kind, job.ident, job.cron) for job in jobs], list(bc.DEFAULT_JOBS))


class PublishTests(unittest.TestCase):
    def test_loopback_moves_and_lan_publish_stays(self) -> None:
        text = "PublishPort=127.0.0.1:9898:9898\nPublishPort=192.168.1.110:9898:9898\n"
        ports = bc.desired_publish(text)
        self.assertEqual(ports, ["192.168.1.110:9898:9898", "127.0.0.1:19898:9898"])
        rendered = bc.dropin_text(ports)
        self.assertIn("PublishPort=\n", rendered)
        self.assertNotIn("127.0.0.1:9898:9898", rendered)


class StackTests(unittest.TestCase):
    def test_on_and_off_order(self) -> None:
        remote = Recorder()
        stack = bc.Stack(remote)
        stack.power_on()
        self.assertEqual(
            remote.calls,
            [
                "disk on",
                "wait-disk ready",
                "restic start",
                "wait-restic",
                "backrest start",
                "wait-api",
            ],
        )
        remote.calls.clear()
        stack.power_off()
        self.assertEqual(
            remote.calls,
            ["backrest stop", "restic stop", "disk off", "wait-disk off"],
        )

    def test_running_job_refuses_shutdown(self) -> None:
        remote = Recorder()
        remote.running = True
        with self.assertRaises(bc.Busy):
            bc.Stack(remote).power_off()
        self.assertEqual(remote.calls, [])


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.running = False

    def disk(self, action: str) -> str:
        self.calls.append(f"disk {action}")
        return "off\n" if action == "off" else "ready\n"

    def wait_disk(self, want: str) -> None:
        self.calls.append(f"wait-disk {want}")

    def restic(self, action: str) -> None:
        self.calls.append(f"restic {action}")

    def wait_restic(self) -> None:
        self.calls.append("wait-restic")

    def backrest(self, action: str) -> None:
        self.calls.append(f"backrest {action}")

    def wait_api(self) -> None:
        self.calls.append("wait-api")

    def jobs_running(self) -> bool:
        return self.running


class RemoteScriptTests(unittest.TestCase):
    def test_allow_list_is_the_script(self) -> None:
        text = (ROOT / "backup-remote").read_text(encoding="utf-8")
        for command in bc.ALLOWED:
            self.assertIn(f'"{command}"', text)
        self.assertNotIn("sh -c", text)
        self.assertNotIn("eval ", text)

    def test_anything_else_is_denied(self) -> None:
        script = ROOT / "backup-remote"
        for command in ("", "bash", "disk on; reboot", "restic-rest start extra", "disk status; id"):
            run = subprocess.run(
                ["/bin/sh", str(script)],
                check=False,
                capture_output=True,
                text=True,
                env={"SSH_ORIGINAL_COMMAND": command, "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(run.returncode, 1, command)
            self.assertEqual(run.stderr.strip(), "denied")


class GateTests(unittest.TestCase):
    def test_failed_shutdown_is_off_when_backrest_is_stopped(self) -> None:
        gate = bc.Gate()
        gate.phase = "on"

        def stop() -> None:
            raise TimeoutError("D: stayed pending, wanted off")

        with patch.object(bc, "backrest_active", return_value=False):
            with self.assertRaises(TimeoutError):
                gate.ensure_off(stop)
        self.assertEqual(gate.phase, "off")


class ProxyTests(unittest.TestCase):
    def test_browser_host_is_proxied_and_widget_host_is_not_a_wake(self) -> None:
        body = b'{"ok":true}'

        class Backend(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                return

        backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(backend.server_close)
        self.addCleanup(backend.shutdown)
        remote = Recorder()
        controller = bc.Controller(remote)  # type: ignore[arg-type]
        controller.gate.phase = "on"
        previous = bc.UPSTREAM_PORT
        bc.UPSTREAM_PORT = backend.server_address[1]
        self.addCleanup(setattr, bc, "UPSTREAM_PORT", previous)

        front = ThreadingHTTPServer(("127.0.0.1", 0), type("H", (bc.Handler,), {"controller": controller}))
        front_thread = threading.Thread(target=front.serve_forever, daemon=True)
        front_thread.start()
        self.addCleanup(front.server_close)
        self.addCleanup(front.shutdown)

        conn = HTTPConnection("127.0.0.1", front.server_address[1], timeout=5)
        conn.request("POST", "/v1.Backrest/GetConfig", b"{}", {"Host": "backup.home.lan", "Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(json.loads(resp.read()), {"ok": True})
        self.assertTrue(controller.hold.interactive)
        conn.close()
        stamp = controller.hold.last_activity

        quiet = HTTPConnection("127.0.0.1", front.server_address[1], timeout=5)
        quiet.request(
            "POST",
            "/v1.Backrest/GetConfig",
            b"{}",
            {"Host": "169.254.1.2:9898", "Content-Type": "application/json"},
        )
        other = quiet.getresponse()
        other.read()
        quiet.close()
        self.assertEqual(other.status, 200)
        self.assertEqual(controller.hold.last_activity, stamp)


if __name__ == "__main__":
    unittest.main()
