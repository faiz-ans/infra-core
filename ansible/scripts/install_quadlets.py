#!/usr/bin/env python3
"""Render catalog files for one host: resolve vars, strip K8s-only kinds."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.quadlet_render import QuadletRenderError, populate_service  # noqa: E402
from lib.quadlet import read_utf8  # noqa: E402
from lib.secrets import load_secrets  # noqa: E402
from lib.topology import all_services, load_desired  # noqa: E402


_VOLUME = re.compile(r"^Volume=([^:\n]+):", re.M)
_HOST_PATH = re.compile(r"(?m)^[ \t]*path:[ \t]*(\S+)\s*$")


def _host_volume_dirs(text: str) -> set[str]:
    """Absolute host paths a unit bind-mounts. Missing ones are created before start."""
    found: set[str] = set()
    for rx in (_VOLUME, _HOST_PATH):
        for match in rx.finditer(text):
            path = match.group(1).strip().strip("\"'")
            if path.startswith("/"):
                found.add(path)
    return found


def main() -> int:
    desired = load_desired(Path(sys.argv[1]))
    host_name = sys.argv[2]
    dest = Path(sys.argv[3])
    secrets_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    secrets = load_secrets(secrets_path) if secrets_path and secrets_path.is_file() else None
    dest.mkdir(parents=True, exist_ok=True)
    volume_dirs: set[tuple[str, str]] = set()
    components = ROOT / "components"
    for svc in all_services(desired):
        if svc.get("host") != host_name:
            continue
        src = components / (svc.get("component") or svc["key"])
        if not src.is_dir():
            continue
        out = dest / svc["name"]
        try:
            populate_service(out, desired, svc, secrets)
        except QuadletRenderError as exc:
            print(exc, file=sys.stderr)
            return 1
        owner = str(svc.get("user") or "")
        for path in out.rglob("*"):
            if not path.is_file():
                continue
            text = read_utf8(path)
            if text is None:
                continue
            for volume in _host_volume_dirs(text):
                volume_dirs.add((owner, volume))
    lines = [f"{owner}|{path}" for owner, path in sorted(volume_dirs)]
    (dest / "volume-dirs.txt").write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
