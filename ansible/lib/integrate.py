"""Wire OpenCloud to Collabora and Radicale only while those services are placed."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .generate import authelia_label, domain_of
from .resolve import LOOPBACK
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


def _env_line(name: str, value: str) -> str:
    # Quadlet splits an unquoted Environment value on spaces.
    if re.search(r"[\s\"]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'Environment={name}="{escaped}"'
    return f"Environment={name}={value}"


def _replace_env(text: str, name: str, value: str) -> str:
    line = _env_line(name, value)
    pattern = re.compile(rf"^Environment={re.escape(name)}=.*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return _insert_before_service(text, [line])


def _replace_addhost(text: str, prefix: str, host: str, ip: str) -> str:
    line = f"AddHost={host}:{ip}"
    pattern = re.compile(rf"^AddHost={re.escape(prefix)}\S*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    if line in text.splitlines():
        return text
    return _insert_before_service(text, [line])


def _reach_ip(desired: dict[str, Any], service: dict[str, Any]) -> str:
    """Address this container uses for public HTTPS.

    A container on the ingress host cannot hairpin to that host's LAN :443.
    Pasta exposes the host loopback as 169.254.1.2, and lan-bind redirects it
    to Caddy. Any other host reaches the ingress LAN address directly.
    """
    ingress = ingress_host(desired) or {}
    if service.get("host") and ingress.get("name") and service.get("host") == ingress.get("name"):
        return LOOPBACK
    return str(ingress.get("ip") or "")


def _unit(directory: Path) -> Path:
    found = sorted(directory.glob("*.container"))
    if len(found) != 1:
        raise ValueError(f"{directory} has {len(found)} container units")
    return found[0]


_COLLABORA_PARAMS = (
    "--o:ssl.enable=false --o:ssl.termination=true "
    "--o:ssl.ssl_verification=false --o:welcome.enable=false"
)


def _opencloud(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    ingress = ingress_host(desired) or {}
    remote = bool(service.get("host") and ingress.get("name") and service.get("host") != ingress.get("name"))
    collaborators = _placed(desired, "collabora")
    if collaborators or remote:
        reach = _reach_ip(desired, service)
        cloud = _host_label(service, desired)
        auth = f"{authelia_label(desired)}.{domain_of(desired)}"
        if reach:
            text = _replace_env(text, "OC_URL", f"https://{cloud}")
            text = _replace_env(text, "OC_DOMAIN", cloud)
            text = _replace_env(text, "IDP_DOMAIN", auth)
            text = _replace_env(text, "OC_OIDC_ISSUER", f"https://{auth}")
            text = _replace_addhost(text, "cloud.", cloud, reach)
            text = _replace_addhost(text, "auth.", auth, reach)
        if collaborators and reach:
            office = _host_label(collaborators[0], desired)
            text = _insert_before_service(
                text,
                [
                    f"AddHost={office}:{reach}",
                    f"Environment=COLLABORA_DOMAIN={office}",
                    f"Environment=COLLABORATION_APP_ADDR=https://{office}",
                    f"Environment=COLLABORATION_WOPI_SRC=https://{cloud}",
                    "Environment=COLLABORATION_APP_PROOF_DISABLE=true",
                    "Environment=COLLABORATION_APP_INSECURE=true",
                    "Environment=COLLABORATION_CS3API_DATAGATEWAY_INSECURE=true",
                    "Environment=OC_ADD_RUN_SERVICES=collaboration",
                ],
            )
    if remote and "PublishPort=${host.ip}:9200:9200" not in text:
        text = _insert_before_service(text, ["PublishPort=${host.ip}:9200:9200"])
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
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    params = _COLLABORA_PARAMS
    lines: list[str] = []
    clouds = _placed(desired, "opencloud")
    if clouds:
        cloud = _host_label(clouds[0], desired)
        reach = _reach_ip(desired, service)
        params += f" --o:net.frame_ancestors={cloud} --o:net.lok_allow.host[14]={cloud}"
        if reach:
            auth = f"{authelia_label(desired)}.{domain_of(desired)}"
            lines = [
                f"AddHost={cloud}:{reach}",
                f"AddHost={auth}:{reach}",
                f"Environment=aliasgroup1=https://{cloud}",
            ]
    text = _replace_env(text, "extra_params", params)
    if lines:
        text = _insert_before_service(text, lines)
    unit.write_text(text, encoding="utf-8")


def _radicale_needs_lan(desired: dict[str, Any], service: dict[str, Any]) -> bool:
    """Caddy or OpenCloud on another host must connect to this host's address."""
    ingress = ingress_host(desired) or {}
    if ingress.get("name") and service.get("host") != ingress.get("name"):
        return True
    return any(peer.get("host") != service.get("host") for peer in _placed(desired, "opencloud"))


def _radicale(directory: Path, desired: dict[str, Any], service: dict[str, Any]) -> None:
    unit = _unit(directory)
    text = unit.read_text(encoding="utf-8")
    lines: list[str] = []
    if "PublishPort=127.0.0.1:5232:5232" not in text:
        lines.append("PublishPort=127.0.0.1:5232:5232")
    if _radicale_needs_lan(desired, service) and "PublishPort=${host.ip}:5232:5232" not in text:
        lines.append("PublishPort=${host.ip}:5232:5232")
    if lines:
        text = _insert_before_service(text, lines)
    unit.write_text(text, encoding="utf-8")


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
