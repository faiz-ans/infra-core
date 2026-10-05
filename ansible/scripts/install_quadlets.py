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
from lib.integrate import apply_placed_integrations  # noqa: E402
from lib.pod import apply_container_overlay, apply_pod_overlay  # noqa: E402
from lib.quadlet import read_utf8, strip_yaml_text  # noqa: E402
from lib.resolve import account_ids, bind, proxy_port, render  # noqa: E402
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


def _host_component_dir(svc: dict) -> str:
    """Path on the workload host. The render directory is only on the operator machine."""
    name = svc["name"]
    if svc.get("privilege") == "rootful":
        return f"/etc/containers/systemd/{name}"
    user = svc.get("user") or "root"
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
    volume_dirs: set[tuple[str, str]] = set()
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
        raw = svc.get("raw") or {}
        pod_overlay = raw.get("pod")
        container_overlay = raw.get("container")
        pod_file = out / "pod.yaml"
        units = list(out.glob("*.container"))
        if pod_overlay:
            if not pod_file.is_file():
                print(f"{svc['name']} pod overlay requires pod.yaml", file=sys.stderr)
                return 1
            apply_pod_overlay(pod_file, pod_overlay)
        if container_overlay:
            if len(units) != 1:
                print(f"{svc['name']} container overlay requires one .container", file=sys.stderr)
                return 1
            try:
                rendered_unit = apply_container_overlay(units[0].read_text(encoding="utf-8"), container_overlay)
            except ValueError as exc:
                print(f"{svc['name']}: {exc}", file=sys.stderr)
                return 1
            units[0].write_text(rendered_unit, encoding="utf-8")
        if str(svc.get("key") or "") == "authelia" and policy(desired)["ldap"] == "openldap":
            unit = out / "authelia.container"
            if unit.is_file():
                unit.write_text(
                    inject_authelia_ldap_password(unit.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
        apply_placed_integrations(out, desired, svc)
        mapping["component.dir"] = _host_component_dir(svc)
        uid, gid = account_ids(host, str(svc.get("user") or ""))
        for path in out.rglob("*"):
            if not path.is_file():
                continue
            text = read_utf8(path)
            if text is None:
                continue
            svc_mapping = dict(mapping)
            svc_mapping["host.operations.workload.user"] = str(svc.get("user") or "")
            svc_mapping["host.operations.workload.uid"] = uid
            svc_mapping["host.operations.workload.gid"] = gid
            svc_mapping["host.operations.workload.proxy_port"] = proxy_port(host, str(svc.get("user") or ""))
            primary = str((svc.get("subdomain") or {}).get("primary") or "")
            domain = mapping.get("site.env.domain") or ""
            if primary and domain:
                svc_mapping["service.public_host"] = f"{primary}.{domain}"
            try:
                rendered = render(
                    text,
                    svc_mapping,
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
            owner = str(svc.get("user") or "")
            for volume in _host_volume_dirs(rendered):
                volume_dirs.add((owner, volume))
        (out / ".privilege").write_text(svc.get("privilege") or "rootless", encoding="utf-8")
    lines = [f"{owner}|{path}" for owner, path in sorted(volume_dirs)]
    (dest / "volume-dirs.txt").write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
