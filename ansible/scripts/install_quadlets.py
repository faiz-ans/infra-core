#!/usr/bin/env python3
"""Render catalog files for one host: resolve vars, strip K8s-only kinds."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.pod import apply_pod_overlay  # noqa: E402
from lib.quadlet import strip_yaml_text  # noqa: E402
from lib.resolve import bind, render  # noqa: E402
from lib.secrets import SecretError, load_secrets  # noqa: E402
from lib.topology import all_services, host_by_name, load_desired  # noqa: E402


def main() -> int:
    desired = load_desired(Path(sys.argv[1]))
    host_name = sys.argv[2]
    dest = Path(sys.argv[3])
    secrets_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    secrets = load_secrets(secrets_path) if secrets_path and secrets_path.is_file() else None
    host = host_by_name(desired, host_name) or {}
    mapping = bind(desired, host)
    dest.mkdir(parents=True, exist_ok=True)
    components = ROOT / "components"
    for svc in all_services(desired):
        if svc.get("host") != host_name:
            continue
        src = components / (svc.get("component") or svc["key"])
        if not src.is_dir():
            continue
        out = dest / svc["name"]
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(src, out, ignore=shutil.ignore_patterns("MANIFEST.toml"))
        overlay = (svc.get("raw") or {}).get("pod")
        if overlay:
            pod_file = out / "pod.yaml"
            if not pod_file.is_file():
                print(f"{svc['name']} pod overlay requires pod.yaml", file=sys.stderr)
                return 1
            apply_pod_overlay(pod_file, overlay)
        mapping["component.dir"] = str(out)
        for path in out.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                rendered = render(
                    text,
                    mapping,
                    service=str(svc.get("key") or ""),
                    host=host_name,
                    secrets=secrets,
                )
            except SecretError as exc:
                print(exc, file=sys.stderr)
                return 1
            if path.suffix in {".yaml", ".yml"} and "kind:" in rendered:
                rendered = strip_yaml_text(rendered)
            path.write_text(rendered, encoding="utf-8")
        (out / ".privilege").write_text(svc.get("privilege") or "rootless", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
