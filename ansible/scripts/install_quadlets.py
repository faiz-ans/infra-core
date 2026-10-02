#!/usr/bin/env python3
"""Render catalog files for one host: resolve vars, strip K8s-only kinds."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.generate import inject_authelia_ldap_password  # noqa: E402
from lib.pod import apply_pod_overlay  # noqa: E402
from lib.quadlet import read_utf8, strip_yaml_text  # noqa: E402
from lib.resolve import bind, render  # noqa: E402
from lib.secrets import SecretError, load_secrets  # noqa: E402
from lib.topology import all_services, host_by_name, load_desired, policy  # noqa: E402


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


def _host_component_dir(host: dict, svc: dict) -> str:
    """Path on the workload host. The render directory is only on the operator machine."""
    name = svc["name"]
    if svc.get("privilege") == "rootful":
        return f"/etc/containers/systemd/{name}"
    user = ((host.get("operations") or {}).get("workload") or {}).get("user") or "root"
    return f"/home/{user}/.config/containers/systemd/{name}"


def main() -> int:
    desired = load_desired(Path(sys.argv[1]))
    host_name = sys.argv[2]
    dest = Path(sys.argv[3])
    secrets_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    secrets = load_secrets(secrets_path) if secrets_path and secrets_path.is_file() else None
    host = host_by_name(desired, host_name) or {}
    mapping = bind(desired, host)
    dest.mkdir(parents=True, exist_ok=True)
    volume_dirs: set[str] = set()
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
        if str(svc.get("key") or "") == "authelia" and policy(desired)["ldap"] == "openldap":
            pod_file = out / "pod.yaml"
            if pod_file.is_file():
                pod_file.write_text(
                    inject_authelia_ldap_password(pod_file.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
        mapping["component.dir"] = _host_component_dir(host, svc)
        for path in out.rglob("*"):
            if not path.is_file():
                continue
            text = read_utf8(path)
            if text is None:
                continue
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
            volume_dirs.update(_host_volume_dirs(rendered))
        (out / ".privilege").write_text(svc.get("privilege") or "rootless", encoding="utf-8")
    (dest / "volume-dirs.txt").write_text("\n".join(sorted(volume_dirs)) + ("\n" if volume_dirs else ""), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
