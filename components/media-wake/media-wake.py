#!/usr/bin/env python3
"""Hold Sablier sessions for a Seerr grab, then for the import, then for seeding.

Seerr's Radarr server URL is http://media-wake:7878 and its Sonarr server URL is
http://media-wake:8989. A request Seerr sends here asks Sablier to start the
units, waits until they answer, and forwards the call. Status polls do not
start anything.

Sablier 1.18 has one expiration per unit and no way to end it early. This
process refreshes a 5 minute session (the same idle time a browser visit gets)
while it still needs the unit. When it stops refreshing, the unit stops after
that session unless a browser visit is still refreshing it. A direct systemctl
start is not a session, and this Sablier stops those.

qBittorrent's WebUI login is not in the site secrets. Write two lines to
/var/lib/media-wake/qbit.env:

    QBIT_USERNAME=admin
    QBIT_PASSWORD=the-webui-password

Until that file exists, a grabbed torrent keeps qBittorrent's session up,
because the ratio cannot be read.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

SABLIER = os.environ.get("SABLIER_URL", "http://sablier:10000").rstrip("/")
SESSION = os.environ.get("SESSION_DURATION", "5m")
SABLIER_TIMEOUT = os.environ.get("SABLIER_TIMEOUT", "3m")
STATE_PATH = os.environ.get("STATE_PATH", "/var/lib/media-wake/state.json")
QBIT_ENV = os.environ.get("QBIT_ENV", "/var/lib/media-wake/qbit.env")
QUIET_S = float(os.environ.get("QUIET_SECONDS", "30"))
IMPORT_TIMEOUT_S = float(os.environ.get("IMPORT_TIMEOUT_SECONDS", "600"))
REFRESH_S = float(os.environ.get("REFRESH_SECONDS", "50"))
LOOP_S = float(os.environ.get("LOOP_SECONDS", "15"))
RATIO = float(os.environ.get("SEED_RATIO", "1.0"))

UNITS = {
    "radarr": "radarr.service",
    "sonarr": "sonarr.service",
    "prowlarr": "prowlarr.service",
    "flaresolverr": "flaresolverr.service",
    "qbittorrent": "qbittorrent.service",
}
UPSTREAM = {
    "radarr": os.environ.get("RADARR_URL", "http://radarr:7878"),
    "sonarr": os.environ.get("SONARR_URL", "http://sonarr:8989"),
}
LISTEN = {"radarr": 7878, "sonarr": 8989}
PING = {
    "radarr": "http://radarr:7878/ping",
    "sonarr": "http://sonarr:8989/ping",
    "prowlarr": "http://prowlarr:9696/ping",
    "flaresolverr": "http://flaresolverr:8191/",
    "qbittorrent": "http://qbittorrent:8081/api/v2/app/version",
}
# Started with Prowlarr for a search, and released when that grab window ends.
SEARCH = {"prowlarr", "flaresolverr", "qbittorrent"}
API = {
    "radarr": "http://radarr:7878/api/v3",
    "sonarr": "http://sonarr:8989/api/v3",
}
QBIT = os.environ.get("QBIT_URL", "http://qbittorrent:8081")

DOWNLOADING = {
    "downloading",
    "metaDL",
    "stalledDL",
    "forcedDL",
    "queuedDL",
    "checkingDL",
    "allocating",
    "moving",
}
SEEDING = {"uploading", "stalledUP", "forcedUP", "queuedUP", "checkingUP"}
WAKE_PARTS = (
    "/qualityprofile",
    "/rootfolder",
    "/languageprofile",
    "/lookup",
    "/release",
    "/downloadclient",
    "/tag",
)
# Seerr's server test reads profiles and root folders. Those only need the arr
# app. A grab also needs Prowlarr and qBittorrent, and Seerr will not wait for
# those to cold-start (its client timeout is 10 seconds).
GRAB_PARTS = ("/lookup", "/release", "/command")


def log(message: str) -> None:
    print(f"media-wake: {message}", flush=True)


def wakes(method: str, path: str) -> bool:
    """A Seerr request modal or a grab. A status poll does not."""
    if method.upper() != "GET":
        return True
    bare = path.split("?", 1)[0]
    return any(part in bare for part in WAKE_PARTS)


def wake_targets(method: str, path: str, app: str) -> set[str]:
    """Who this request must wait for. A grab waits for the whole set."""
    bare = path.split("?", 1)[0]
    if method.upper() != "GET" or any(part in bare for part in GRAB_PARTS):
        return {app, *SEARCH}
    return {app}


def torrent_working(state: str, progress: float, ratio: float) -> bool:
    """True while this torrent is downloading, or seeding and still under the ratio.

    Paused and stopped torrents are the user's. They do not keep qBittorrent up.
    """
    if state in {"pausedDL", "pausedUP", "stoppedDL", "stoppedUP", "error", "missingFiles"}:
        return False
    if progress < 0.999:
        return state in DOWNLOADING
    return ratio < RATIO and state in SEEDING


def decide(snap: dict[str, Any]) -> set[str]:
    """Units whose Sablier session this process should refresh."""
    units: set[str] = set()
    grab_open = bool(snap["grab_apps"]) and (
        snap["inflight"] > 0 or not snap["quiet"] or not snap["polled"] or snap["pending"]
    )
    if grab_open:
        units.update(snap["grab_apps"])
        units.update(SEARCH)
    for job in snap["jobs"]:
        if job["failed"]:
            if job["seeding"]:
                units.add("qbittorrent")
            continue
        if not job["imported"] and job["complete"]:
            units.add(job["app"])
            units.add("qbittorrent")
            continue
        if not job["imported"] and not (job.get("seen") and not job["seeding"]):
            units.add("qbittorrent")
        elif job["seeding"]:
            units.add("qbittorrent")
    if snap["foreign_active"] or (snap["qbit_unknown"] and snap["jobs"]):
        units.add("qbittorrent")
    return units


class Gate:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.inflight = 0
        self.grab_apps: set[str] = set()
        self.last_interactive = 0.0
        self.polled_after = 0.0
        self.pending = False
        self.jobs: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, str] = {}
        self.foreign_active = False
        self.qbit_unknown = True
        self.held: set[str] = set()
        self.refreshed: dict[str, float] = {}
        self.status_cache: dict[str, bytes] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(STATE_PATH, encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw.get("keys"), dict):
            self.keys = {str(k): str(v) for k, v in raw["keys"].items() if v}
        jobs = raw.get("jobs")
        if isinstance(jobs, dict):
            for download_id, job in jobs.items():
                if isinstance(job, dict) and job.get("app") in UPSTREAM:
                    self.jobs[str(download_id).lower()] = {
                        "app": job["app"],
                        "imported": bool(job.get("imported")),
                        "failed": bool(job.get("failed")),
                        "complete": bool(job.get("complete")),
                        "seeding": bool(job.get("seeding", not job.get("imported"))),
                        "seen": bool(job.get("seen")),
                        "complete_at": float(job.get("complete_at") or 0),
                    }

    def save(self) -> None:
        parent = os.path.dirname(STATE_PATH)
        os.makedirs(parent, exist_ok=True)
        payload = {"keys": self.keys, "jobs": self.jobs}
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE_PATH)

    def learn_key(self, app: str, headers: Any, path: str) -> None:
        key = headers.get("X-Api-Key") or ""
        if not key:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            found = query.get("apikey") or query.get("apiKey") or []
            key = found[0] if found else ""
        if not key:
            return
        with self.lock:
            if self.keys.get(app) == key:
                return
            self.keys[app] = key
            self.save()
        log(f"saved {app} api key from a proxied request")

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self.lock:
            quiet = bool(self.grab_apps) and (now - self.last_interactive) >= QUIET_S
            polled = self.polled_after >= self.last_interactive and self.last_interactive > 0
            return {
                "grab_apps": set(self.grab_apps),
                "inflight": self.inflight,
                "quiet": quiet,
                "polled": polled,
                "pending": self.pending,
                "jobs": [dict(job) for job in self.jobs.values()],
                "foreign_active": self.foreign_active,
                "qbit_unknown": self.qbit_unknown,
            }

    def begin(self, app: str) -> None:
        with self.lock:
            self.inflight += 1
            self.grab_apps.add(app)
            self.last_interactive = time.monotonic()

    def end(self) -> None:
        with self.lock:
            self.inflight = max(0, self.inflight - 1)
            self.last_interactive = time.monotonic()

    def note_jobs(self, app: str, records: list[dict[str, Any]], history: dict[str, str]) -> None:
        now = time.time()
        with self.lock:
            self.polled_after = time.monotonic()
            self.pending = False
            seen: set[str] = set()
            for record in records:
                download_id = str(record.get("downloadId") or "").lower()
                state = str(record.get("trackedDownloadState") or "")
                status = str(record.get("status") or "")
                if not download_id:
                    if status not in {"completed", "failed"}:
                        self.pending = True
                    continue
                seen.add(download_id)
                job = self.jobs.setdefault(
                    download_id,
                    {
                        "app": app,
                        "imported": False,
                        "failed": False,
                        "complete": False,
                        "seeding": True,
                        "seen": False,
                        "complete_at": 0,
                    },
                )
                job["app"] = app
                if state == "imported" or history.get(download_id) == "downloadFolderImported":
                    job["imported"] = True
                if state in {"failed", "failedPending"} or status == "failed" or history.get(download_id) == "downloadFailed":
                    job["failed"] = True
                if job["complete"] and job["complete_at"] and not job["imported"] and not job["failed"]:
                    if now - job["complete_at"] > IMPORT_TIMEOUT_S:
                        job["failed"] = True
                        log(f"{app} did not import {download_id} within {int(IMPORT_TIMEOUT_S)}s")
            for download_id, job in self.jobs.items():
                if job["app"] != app or download_id in seen or job["imported"] or job["failed"]:
                    continue
                event = history.get(download_id)
                if event == "downloadFolderImported":
                    job["imported"] = True
                elif event == "downloadFailed":
                    job["failed"] = True
            if (
                self.inflight == 0
                and self.grab_apps
                and not self.pending
                and (time.monotonic() - self.last_interactive) >= QUIET_S
            ):
                self.grab_apps.clear()
            self.save()

    def note_torrents(self, torrents: list[dict[str, Any]] | None) -> None:
        now = time.time()
        with self.lock:
            if torrents is None:
                self.qbit_unknown = True
                self.foreign_active = False
                self.save()
                return
            self.qbit_unknown = False
            known = set(self.jobs)
            foreign = False
            present = set()
            for item in torrents:
                download_id = str(item.get("hash") or "").lower()
                progress = float(item.get("progress") or 0)
                ratio = float(item.get("ratio") or 0)
                state = str(item.get("state") or "")
                if ratio < 0:
                    ratio = RATIO
                working = torrent_working(state, progress, ratio)
                if download_id and download_id not in known and working:
                    foreign = True
                job = self.jobs.get(download_id)
                if not job:
                    continue
                present.add(download_id)
                job["seen"] = True
                complete = progress >= 0.999
                if complete and not job["complete"]:
                    job["complete"] = True
                    job["complete_at"] = now
                    log(f"{job['app']} torrent {download_id} finished downloading")
                job["seeding"] = working and ratio < RATIO and not job["failed"]
                if not working and ratio >= RATIO:
                    job["seeding"] = False
            for download_id, job in self.jobs.items():
                if download_id not in present and job.get("seen"):
                    job["seeding"] = False
            self.foreign_active = foreign
            self.jobs = {
                download_id: job
                for download_id, job in self.jobs.items()
                if not (job["imported"] or job["failed"]) or job["seeding"]
            }
            self.save()

    def cached_status(self, app: str) -> bytes | None:
        with self.lock:
            return self.status_cache.get(app)

    def store_status(self, app: str, path: str, body: bytes) -> None:
        if "/system/status" not in path.split("?", 1)[0]:
            return
        with self.lock:
            self.status_cache[app] = body


GATE = Gate()


def qbit_login() -> tuple[str, str]:
    username = os.environ.get("QBIT_USERNAME", "")
    password = os.environ.get("QBIT_PASSWORD", "")
    try:
        with open(QBIT_ENV, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "QBIT_USERNAME" and not username:
                    username = value.strip()
                elif key.strip() == "QBIT_PASSWORD" and not password:
                    password = value.strip()
    except OSError:
        pass
    return username, password


def http_json(url: str, headers: dict[str, str] | None = None, data: bytes | None = None, timeout: float = 20) -> Any:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def ping(app: str, timeout: float = 3) -> bool:
    """True when the app's HTTP server answers.

    qBittorrent's version URL returns 403 until a WebUI login. That response
    means the server is up. A refused connection or a timeout means it is not.
    """
    try:
        with urllib.request.urlopen(PING[app], timeout=timeout) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError:
        return True
    except (OSError, urllib.error.URLError):
        return False


def session(app: str) -> bool:
    """Ask Sablier to start this unit and push its expiration out by one idle period."""
    query = urllib.parse.urlencode(
        {
            "names": UNITS[app],
            "session_duration": SESSION,
            "timeout": SABLIER_TIMEOUT,
        }
    )
    url = f"{SABLIER}/api/strategies/blocking?{query}"
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=200) as response:
            status = response.headers.get("X-Sablier-Session-Status", "")
            body = response.read()
    except (OSError, urllib.error.URLError) as exc:
        log(f"sablier {app}: {exc}")
        return False
    if status == "ready":
        return True
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}
    ready = status == "ready" or str(payload.get("status") or "") == "ready"
    if not ready:
        log(f"sablier {app} is {status or payload.get('status') or 'not ready'}")
    return ready


def wait_ready(apps: set[str]) -> bool:
    deadline = time.monotonic() + 90
    pending = set(apps)
    while pending and time.monotonic() < deadline:
        pending = {app for app in pending if not ping(app)}
        if pending:
            time.sleep(1)
    if pending:
        log(f"still not listening: {', '.join(sorted(pending))}")
        return False
    return True


def wake(app: str, targets: set[str]) -> bool:
    """Start the units this request needs and wait until those are listening.

    The supervisor still holds Prowlarr and qBittorrent for a grab window. This
    wait is only the units Seerr cannot proceed without.
    """
    GATE.begin(app)
    ok = True
    for name in sorted(targets):
        if not session(name):
            ok = False
        else:
            GATE.refreshed[name] = time.monotonic()
    if ok:
        ok = wait_ready(targets)
    return ok


def refresh(units: set[str]) -> None:
    now = time.monotonic()
    for app in sorted(units):
        if now - GATE.refreshed.get(app, 0) < REFRESH_S and ping(app):
            continue
        if session(app):
            GATE.refreshed[app] = time.monotonic()


def arr_records(app: str) -> tuple[list[dict[str, Any]], dict[str, str]] | None:
    key = GATE.keys.get(app)
    if not key or not ping(app):
        return None
    headers = {"X-Api-Key": key}
    try:
        extra = "includeUnknownMovieItems=true" if app == "radarr" else "includeUnknownSeriesItems=true"
        queue = http_json(f"{API[app]}/queue?pageSize=250&{extra}", headers)
        history = http_json(f"{API[app]}/history?pageSize=100", headers)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        log(f"{app} queue: {exc}")
        return None
    records = queue.get("records") if isinstance(queue, dict) else None
    events = history.get("records") if isinstance(history, dict) else None
    by_id: dict[str, str] = {}
    for event in events or []:
        download_id = str(event.get("downloadId") or "").lower()
        kind = str(event.get("eventType") or "")
        if download_id and kind in {"downloadFolderImported", "downloadFailed"}:
            by_id.setdefault(download_id, kind)
    return list(records or []), by_id


def qbit_torrents() -> list[dict[str, Any]] | None:
    username, password = qbit_login()
    if not username:
        return None
    if not ping("qbittorrent"):
        return None
    form = urllib.parse.urlencode({"username": username, "password": password}).encode()
    try:
        request = urllib.request.Request(
            f"{QBIT}/api/v2/auth/login",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": f"{QBIT}/"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            cookie = response.headers.get("Set-Cookie", "")
        info = urllib.request.Request(f"{QBIT}/api/v2/torrents/info", headers={"Cookie": cookie.split(";", 1)[0]})
        with urllib.request.urlopen(info, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        log(f"qbit: {exc}")
        return None
    return list(payload) if isinstance(payload, list) else None


def supervise() -> None:
    missing_logged = False
    while True:
        username, _password = qbit_login()
        if not username and not missing_logged:
            log(f"no qBittorrent login in {QBIT_ENV}; seeded ratio cannot be read, so qBittorrent stays up after a grab")
            missing_logged = True
        if username:
            missing_logged = False
        snap = GATE.snapshot()
        units = decide(snap)
        if units != GATE.held:
            log(f"holding {', '.join(sorted(units)) or 'nothing'}")
            GATE.held = set(units)
        if units:
            refresh(units)
        for app in ("radarr", "sonarr"):
            if app not in units and app not in GATE.snapshot()["grab_apps"]:
                continue
            scanned = arr_records(app)
            if scanned is not None:
                GATE.note_jobs(app, scanned[0], scanned[1])
        if "qbittorrent" in units or GATE.jobs:
            GATE.note_torrents(qbit_torrents() if username else None)
        time.sleep(LOOP_S)


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
    # Seerr asks for gzip. Forwarding that and then dropping Content-Encoding
    # hands Seerr compressed bytes, which it does not treat as a folder list.
    "accept-encoding",
}


class Proxy(BaseHTTPRequestHandler):
    app = "radarr"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        self._forward()

    def do_POST(self) -> None:
        self._forward()

    def do_PUT(self) -> None:
        self._forward()

    def do_DELETE(self) -> None:
        self._forward()

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        GATE.learn_key(self.app, self.headers, self.path)
        interactive = wakes(self.command, self.path)
        if interactive:
            if not wake(self.app, wake_targets(self.command, self.path, self.app)):
                self._send(503, b"media-wake could not start the download apps\n")
                GATE.end()
                return
        elif not ping(self.app):
            cached = GATE.cached_status(self.app)
            if cached is not None and self.command == "GET" and "/system/status" in self.path:
                self._send(200, cached, "application/json")
                return
            self._send(503, b"asleep\n")
            return
        url = UPSTREAM[self.app] + self.path
        headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP}
        headers["Host"] = urllib.parse.urlparse(UPSTREAM[self.app]).netloc
        request = urllib.request.Request(url, data=body, headers=headers, method=self.command)
        try:
            try:
                response = urllib.request.urlopen(request, timeout=180)
                status = response.status
                payload = response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")
            except urllib.error.HTTPError as exc:
                status = exc.code
                payload = exc.read()
                content_type = exc.headers.get("Content-Type", "application/octet-stream")
        except (OSError, urllib.error.URLError) as exc:
            log(f"{self.app} upstream: {exc}")
            self._send(502, b"upstream failed\n")
            if interactive:
                GATE.end()
            return
        if self.command == "GET":
            GATE.store_status(self.app, self.path, payload)
        self._send(status, payload, content_type)
        if interactive:
            GATE.end()

    def _send(self, status: int, payload: bytes, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            return


def serve() -> None:
    log("Seerr Radarr URL is http://media-wake:7878 and Sonarr URL is http://media-wake:8989")
    threading.Thread(target=supervise, name="supervise", daemon=True).start()
    threads = []
    for app, port in LISTEN.items():
        handler = type(f"{app.title()}Proxy", (Proxy,), {"app": app})
        server = ThreadingHTTPServer(("0.0.0.0", port), handler)
        thread = threading.Thread(target=server.serve_forever, name=app, daemon=True)
        thread.start()
        threads.append(thread)
        log(f"listening on {port} for {app}")
    for thread in threads:
        thread.join()


def _self_test() -> None:
    assert wakes("POST", "/api/v3/movie")
    assert wakes("GET", "/api/v3/qualityprofile")
    assert wakes("GET", "/api/v3/movie/lookup?term=foo")
    assert not wakes("GET", "/api/v3/system/status")
    assert wake_targets("GET", "/api/v3/rootfolder", "radarr") == {"radarr"}
    assert wake_targets("GET", "/api/v3/qualityprofile", "sonarr") == {"sonarr"}
    assert wake_targets("POST", "/api/v3/movie", "radarr") == {"radarr", "prowlarr", "flaresolverr", "qbittorrent"}
    assert wake_targets("GET", "/api/v3/movie/lookup?term=a", "radarr") == {"radarr", "prowlarr", "flaresolverr", "qbittorrent"}
    assert not wakes("GET", "/api/v3/queue?pageSize=10")
    assert not wakes("GET", "/api/v3/movie")

    asleep = {
        "grab_apps": set(),
        "inflight": 0,
        "quiet": True,
        "polled": True,
        "pending": False,
        "jobs": [],
        "foreign_active": False,
        "qbit_unknown": False,
    }
    assert decide(asleep) == set()

    grabbing = dict(asleep, grab_apps={"radarr"}, quiet=False, polled=False)
    assert decide(grabbing) == {"radarr", "prowlarr", "flaresolverr", "qbittorrent"}

    downloading = dict(
        asleep,
        jobs=[{"app": "radarr", "imported": False, "failed": False, "complete": False, "seeding": True}],
    )
    assert decide(downloading) == {"qbittorrent"}

    importing = dict(
        asleep,
        jobs=[{"app": "sonarr", "imported": False, "failed": False, "complete": True, "seeding": True}],
    )
    assert decide(importing) == {"sonarr", "qbittorrent"}

    seeding = dict(
        asleep,
        jobs=[{"app": "radarr", "imported": True, "failed": False, "complete": True, "seeding": True}],
    )
    assert decide(seeding) == {"qbittorrent"}

    done = dict(
        asleep,
        jobs=[{"app": "radarr", "imported": True, "failed": False, "complete": True, "seeding": False}],
    )
    assert decide(done) == set()

    paused = dict(
        asleep,
        jobs=[{"app": "radarr", "imported": False, "failed": False, "complete": False, "seeding": False, "seen": True}],
    )
    assert decide(paused) == set()

    assert torrent_working("downloading", 0.4, 0.0)
    assert torrent_working("stalledUP", 1.0, 0.2)
    assert not torrent_working("stalledUP", 1.0, 1.0)
    assert not torrent_working("pausedUP", 1.0, 0.2)
    assert not torrent_working("stoppedDL", 0.4, 0.0)
    print("ok")


if __name__ == "__main__":
    import sys

    if "--self-test" in sys.argv:
        _self_test()
    else:
        serve()
