"""Render one service tree the way SET syncs it.

The Day 2 fingerprint hashes these bytes. A site.yaml edit that no unit reads
does not change the hash, so SET does not restart that service.
"""
from __future__ import annotations

import base64
import posixpath
import re
import shutil
from pathlib import Path
from typing import Any

from .backup import backup_runner, backup_sources
from .generate import inject_authelia_ldap_password
from .integrate import apply_placed_integrations
from .pod import (
    apply_container_overlay,
    apply_pod_overlay,
    ensure_sablier_section,
    inject_sablier_pod_labels,
    sablier_enabled,
)
from .quadlet import read_utf8, strip_yaml_text
from .resolve import account_ids, bind, proxy_port, render
from .secrets import SecretError
from .topology import ROOT, host_by_name, policy, workload_users


class QuadletRenderError(Exception):
    pass


def _icon_data_uri(path: Path) -> str:
    kind = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(path.suffix.lower(), "application/octet-stream")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{kind};base64,{payload}"


def _embed_waiting_icons(out: Path, icons: Path) -> None:
    """Sablier inlines img src that is already in the HTML. The logo src is chosen
    in script after that pass, so a relative URL is requested from the app that
    is still starting. Embed the bytes instead."""
    script = out / "themes" / "js" / "site.js"
    if not script.is_file():
        raise QuadletRenderError("sablier theme script is missing")
    entries = []
    for path in sorted(icons.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        entries.append(f'  "{path.name}": "{_icon_data_uri(path)}"')
    body = "const ICON_FILES = {\n" + ",\n".join(entries) + "\n};\nfunction icon(name) {\n  return ICON_FILES[name] || \"\";\n}"
    text = script.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'function icon\(name\) \{\n  return "images/icons/" \+ name;\n\}',
        body,
        text,
        count=1,
    )
    if count != 1:
        raise QuadletRenderError("sablier theme script has no icon() to embed")
    script.write_text(updated, encoding="utf-8")


def _copy_waiting_assets(out: Path) -> None:
    """Copy Homepage's photo and icons. Sablier will not follow a symlink."""
    images = ROOT / "components" / "homepage" / "images"
    background = images / "background.png"
    icons = images / "icons"
    if not background.is_file():
        raise QuadletRenderError("homepage background image is missing; the Sablier waiting page uses it")
    if not icons.is_dir() or not any(icons.iterdir()):
        raise QuadletRenderError("homepage icons are missing; the Sablier waiting page uses them")
    dest = out / "themes" / "images"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(background, dest / "background.jpg")
    icon_dest = dest / "icons"
    if icon_dest.exists():
        shutil.rmtree(icon_dest)
    shutil.copytree(icons, icon_dest)
    _embed_waiting_icons(out, icon_dest)


def _host_component_dir(svc: dict[str, Any]) -> str:
    """Path on the workload host. The render directory is only on the operator machine."""
    name = svc["name"]
    if svc.get("privilege") == "rootful":
        return f"/etc/containers/systemd/{name}"
    user = svc.get("user") or "root"
    return f"/home/{user}/.config/containers/systemd/{name}"


def populate_service(
    out: Path,
    desired: dict[str, Any],
    svc: dict[str, Any],
    secrets: dict[str, Any] | None,
    *,
    missing_secret: str = "error",
) -> None:
    """Write the synced tree for one service. Raises QuadletRenderError on a bad overlay."""
    component = str(svc.get("component") or svc.get("key") or "")
    src = ROOT / "components" / component
    if not src.is_dir():
        raise QuadletRenderError(f"{svc.get('name')} has no component directory")
    host_name = str(svc.get("host") or "")
    host = host_by_name(desired, host_name) or {}
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("MANIFEST.toml"))
    if component == "sablier":
        _copy_waiting_assets(out)
    raw = svc.get("raw") or {}
    pod_overlay = raw.get("pod")
    container_overlay = raw.get("container")
    pod_file = out / "pod.yaml"
    units = list(out.glob("*.container"))
    name = str(svc.get("name") or "")
    if pod_overlay:
        if not pod_file.is_file():
            raise QuadletRenderError(f"{name} pod overlay requires pod.yaml")
        apply_pod_overlay(pod_file, pod_overlay)
    if container_overlay:
        if len(units) != 1:
            raise QuadletRenderError(f"{name} container overlay requires one .container")
        try:
            rendered_unit = apply_container_overlay(units[0].read_text(encoding="utf-8"), container_overlay)
        except ValueError as exc:
            raise QuadletRenderError(f"{name}: {exc}") from exc
        units[0].write_text(rendered_unit, encoding="utf-8")
    if sablier_enabled(raw):
        for unit in list(out.glob("*.container")):
            text = apply_container_overlay(
                unit.read_text(encoding="utf-8"),
                {"labels": {"sablier.enable": "true"}},
            )
            unit.write_text(ensure_sablier_section(text), encoding="utf-8")
        pod_path = out / "pod.yaml"
        if pod_path.is_file():
            inject_sablier_pod_labels(pod_path)
        for unit in list(out.glob("*.kube")):
            unit.write_text(ensure_sablier_section(unit.read_text(encoding="utf-8")), encoding="utf-8")
    assets = policy(desired)["portal_assets"]
    custom_caddy = bool(assets) or "sablier" in policy(desired)["plugins"]
    if custom_caddy and str(svc.get("key") or "") == "caddy":
        unit = next(out.glob("*.container"), None)
        if unit and unit.is_file():
            text = unit.read_text(encoding="utf-8")
            text = re.sub(r"^Image=.*$", "Image=localhost/caddy-portal:2", text, count=1, flags=re.M)
            if not re.search(r"^Pull=", text, flags=re.M):
                text = text.replace("Image=localhost/caddy-portal:2\n", "Image=localhost/caddy-portal:2\nPull=never\n", 1)
            if assets:
                theme = ROOT / "portal"
                if not (theme / "login.js").is_file():
                    raise QuadletRenderError("portal/login.js is missing")
                dest = out / "portal"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(theme, dest)
            line = f"Volume=${{component.dir}}/portal:{assets}:ro\n"
            if assets and line not in text:
                marker = "\n[Service]\n"
                if marker not in text:
                    raise QuadletRenderError("caddy container unit has no [Service] section for portal assets")
                text = text.replace(marker, "\n" + line + marker, 1)
            unit.write_text(text, encoding="utf-8")
    if str(svc.get("key") or "") == "authelia" and policy(desired)["ldap"] == "openldap":
        unit = out / "authelia.container"
        if unit.is_file():
            unit.write_text(
                inject_authelia_ldap_password(unit.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
    apply_placed_integrations(out, desired, svc)
    mapping = bind(desired, host)
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
        for entry in workload_users(host):
            entry_name = str(entry.get("name") or "")
            if entry_name:
                svc_mapping[f"host.operations.workload.users.{entry_name}.proxy_port"] = proxy_port(host, entry_name)
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
                missing_secret=missing_secret,
            )
        except SecretError as exc:
            raise QuadletRenderError(str(exc)) from exc
        if path.suffix in {".yaml", ".yml"} and "kind:" in rendered:
            rendered = strip_yaml_text(rendered)
        path.write_text(rendered, encoding="utf-8")
    _mount_backup_sources(out, desired, svc)
    (out / ".privilege").write_text(svc.get("privilege") or "rootless", encoding="utf-8")


def _mount_backup_sources(out: Path, desired: dict[str, Any], svc: dict[str, Any]) -> None:
    """Bind each backup source into the engine container. The plan list is first-start only."""
    runner = backup_runner(desired)
    if runner is None or runner.get("key") != svc.get("key") or runner.get("host") != svc.get("host"):
        return
    if runner.get("user") != svc.get("user") or runner.get("name") != svc.get("name"):
        return
    sources, errors = backup_sources(desired)
    if errors:
        raise QuadletRenderError("; ".join(errors))
    unit = next(out.glob("*.container"), None)
    if unit is None or not unit.is_file():
        return
    text = unit.read_text(encoding="utf-8")
    lines = [f"Volume={source['client_path']}:{source['container']}:ro" for source in sources]
    lines.append("Volume=${component.dir}/sources.list:/sources.list:ro")
    # component.dir was already substituted in this file.
    component_dir = ""
    for line in text.splitlines():
        if line.startswith("Volume=") and line.endswith("/seed.sh:/seed.sh:ro"):
            component_dir = posixpath.dirname(line.split(":", 1)[0].removeprefix("Volume="))
            break
    if component_dir:
        lines[-1] = f"Volume={component_dir}/sources.list:/sources.list:ro"
    marker = "\n[Service]\n"
    if marker not in text:
        raise QuadletRenderError("backup container unit has no [Service] section for source mounts")
    block = "\n".join(lines) + "\n"
    if block not in text:
        text = text.replace(marker, "\n" + block + marker, 1)
    unit.write_text(text, encoding="utf-8")
    (out / "sources.list").write_text("".join(f"{source['container']}\n" for source in sources), encoding="utf-8")


def rendered_files(
    desired: dict[str, Any],
    svc: dict[str, Any],
    secrets: dict[str, Any] | None,
) -> dict[str, bytes] | None:
    """Relative path → bytes SET would sync. None when the service has no catalog tree."""
    component = str(svc.get("component") or svc.get("key") or "")
    if not (ROOT / "components" / component).is_dir():
        return None
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / str(svc.get("name") or "service")
        populate_service(out, desired, svc, secrets, missing_secret="name")
        files: dict[str, bytes] = {}
        for path in out.rglob("*"):
            if path.is_file():
                files[path.relative_to(out).as_posix()] = path.read_bytes()
        return files
