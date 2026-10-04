"""Wire OpenCloud to Collabora and Radicale only while those services are placed."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .generate import authelia_label, domain_of
from .topology import all_services, ingress_host


def _placed(desired: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [service for service in all_services(desired) if service.get("key") == key]


def _host_label(service: dict[str, Any], desired: dict[str, Any]) -> str:
    primary = (service.get("subdomain") or {}).get("primary") or service.get("key") or ""
    return f"{primary}.{domain_of(desired)}"


def _insert_before_service(text: str, lines: list[str]) -> str:
    existing = set(text.splitlines())
    fresh = [line for line in lines if line and line not in existing]
    if not fresh:
        return text
    block = "\n".join(fresh) + "\n"
    marker = "\n[Service]\n"
    if marker not in text:
        raise ValueError("container unit has no [Service] section")
    return text.replace(marker, "\n" + block + marker, 1)


def _replace_env(text: str, name: str, value: str) -> str:
    line = f"Environment={name}={value}"
    pattern = re.compile(rf"^Environment={re.escape(name)}=.*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return _insert_before_service(text, [line])


def _unit(directory: Path) -> Path:
    found = sorted(directory.glob("*.container"))
    if len(found) != 1:
        raise ValueError(f"{directory} has {len(found)} container units")
    return found[0]


def _opencloud(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    ingress_ip = str((ingress_host(desired) or {}).get("ip") or "")
    lines: list[str] = []
    collaborators = _placed(desired, "collabora")
    if collaborators and ingress_ip:
        office = _host_label(collaborators[0], desired)
        cloud = _host_label(service, desired)
        lines += [
            f"AddHost={office}:{ingress_ip}",
            f"Environment=COLLABORA_DOMAIN={office}",
            f"Environment=COLLABORATION_APP_ADDR=https://{office}",
            f"Environment=COLLABORATION_WOPI_SRC=https://{cloud}",
            "Environment=COLLABORATION_APP_PROOF_DISABLE=true",
            "Environment=OC_ADD_RUN_SERVICES=collaboration",
        ]
    if lines:
        text = _insert_before_service(text, lines)
    unit.write_text(text, encoding="utf-8")

    proxy = directory / "proxy.yaml"
    policy = directory / "radicale-policy.yaml"
    if proxy.is_file() and policy.is_file() and _placed(desired, "radicale"):
        backend = "http://radicale:5232"
        rad = _placed(desired, "radicale")[0]
        if rad.get("host") != service.get("host") and rad.get("host_ip"):
            backend = f"http://{rad['host_ip']}:5232"
        extra = policy.read_text(encoding="utf-8").replace("http://radicale:5232", backend)
        body = proxy.read_text(encoding="utf-8").rstrip() + "\n\n" + extra
        if not body.endswith("\n"):
            body += "\n"
        proxy.write_text(body, encoding="utf-8")
    if policy.is_file():
        policy.unlink()


def _collabora(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    clouds = _placed(desired, "opencloud")
    if not clouds:
        return
    ingress_ip = str((ingress_host(desired) or {}).get("ip") or "")
    if not ingress_ip:
        return
    cloud = _host_label(clouds[0], desired)
    auth = f"{authelia_label(desired)}.{domain_of(desired)}"
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    text = _replace_env(
        text,
        "extra_params",
        "--o:ssl.enable=false --o:ssl.ssl_termination=true "
        f"--o:welcome.enable=false --o:net.frame_ancestors={cloud}",
    )
    text = _insert_before_service(
        text,
        [
            f"AddHost={cloud}:{ingress_ip}",
            f"AddHost={auth}:{ingress_ip}",
            "Environment=SSL_CERT_FILE=/ca/ca-bundle.crt",
            f"Environment=CADDY_CA_URL=https://{auth}/pki/local-root.crt",
            f"Environment=aliasgroup1=https://{cloud}",
        ],
    )
    unit.write_text(text, encoding="utf-8")


def _radicale(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    clouds = _placed(desired, "opencloud")
    if not clouds or clouds[0].get("host") == service.get("host"):
        return
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    if "PublishPort=" in text:
        return
    unit.write_text(_insert_before_service(text, ["PublishPort=5232:5232"]), encoding="utf-8")


def _grafana(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    unit.write_text(
        _replace_env(text, "GF_SERVER_ROOT_URL", f"https://{_host_label(service, desired)}"),
        encoding="utf-8",
    )


def apply_placed_integrations(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    """Mutate a rendered component tree from the services actually listed."""
    key = str(service.get("key") or "")
    if key == "opencloud":
        _opencloud(directory, desired, service)
    elif key == "collabora":
        _collabora(directory, desired, service)
    elif key == "radicale":
        _radicale(directory, desired, service)
    elif key == "grafana":
        _grafana(directory, desired, service)
