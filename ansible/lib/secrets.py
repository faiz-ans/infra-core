"""Decrypt SOPS/Age on the runner. Never write a host site.env.

Secrets file:

    secrets:
      site:
        authelia:
          session: ...
      hosts:
        core:
          pi-hole:
            web_password: ...

A reference is resolved while rendering one service on one host.

Site, in the service's own unit: `secrets.site.authelia.session`,
`secrets.authelia.session`, and `secrets.session` are the same secret.
Host, in that service's unit: `secrets.hosts.<hostname>.pi-hole.web_password`,
`secrets.host.pi-hole.web_password`, and `secrets.host.web_password` are the
same secret. `host` is the instance's host. The service name is optional only
when it is the service being rendered.

`pi-hole` and `pihole` are the same service. The Podman secret name is
`<service>_<secret>` with hyphens removed from the service (`pihole_web_password`).
Each host receives site secrets plus its own host secrets, so both hosts can
have `pihole_web_password` with different values.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


class SecretError(Exception):
    pass


def load_secrets(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    if "ENC[" in raw or path.name.endswith(".sops.yaml"):
        try:
            proc = subprocess.run(
                ["sops", "-d", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            raw = proc.stdout
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"SOPS decrypt failed for {path}: {exc}") from exc
    import yaml

    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data


def _norm_service(name: str) -> str:
    return name.replace("-", "").replace("_", "").lower()


def _index_services(raw: dict[str, Any], where: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    owners: dict[str, str] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            raise SecretError(f"{where}.{key} must be a mapping of secret names")
        norm = _norm_service(str(key))
        if norm in owners:
            raise SecretError(f"{where} lists both {owners[norm]!r} and {key!r}")
        owners[norm] = str(key)
        indexed[str(key)] = val
    return indexed


def split_secrets(data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    """Return (site services, host → services). Keys beside site/hosts count as site."""
    root = data.get("secrets") if isinstance(data.get("secrets"), dict) else data
    if not isinstance(root, dict):
        return {}, {}
    if isinstance(root.get("site"), dict) or isinstance(root.get("hosts"), dict):
        site_raw = dict(root.get("site") or {})
        for key, val in root.items():
            if key in ("site", "hosts") or not isinstance(val, dict):
                continue
            site_raw.setdefault(key, val)
        hosts_node = root.get("hosts") if isinstance(root.get("hosts"), dict) else {}
        hosts = {
            str(name): _index_services(body, f"secrets.hosts.{name}")
            for name, body in hosts_node.items()
            if isinstance(body, dict)
        }
        return _index_services(site_raw, "secrets.site"), hosts
    site_raw = {k: v for k, v in root.items() if isinstance(v, dict)}
    return _index_services(site_raw, "secrets"), {}


def _find_service(services: dict[str, dict[str, Any]], token: str) -> tuple[str, dict[str, Any]] | None:
    want = _norm_service(token)
    for key, body in services.items():
        if _norm_service(key) == want:
            return key, body
    return None


def _leaf(body: dict[str, Any], parts: list[str]) -> str | None:
    node: Any = body
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, (dict, list)) or node is None:
        return None
    return str(node)


def podman_name(service_key: str, leaf: list[str]) -> str:
    service = service_key.replace("-", "").replace("_", "")
    secret = "_".join(part.replace("-", "_") for part in leaf)
    return f"{service}_{secret}"


def _reference_name(
    consumer: str,
    source_key: str,
    source_host: str,
    instance_host: str,
    written_service: str,
    leaf: list[str],
) -> str:
    """Own secret → pihole_web_password. Another service on this host → homepage_pi-hole_web_password. Another host → homepage_mantle_pi-hole_web_password."""
    own_service = _norm_service(consumer or "") == _norm_service(source_key)
    if not source_host or (own_service and source_host == instance_host):
        return podman_name(source_key, leaf)
    bits = [consumer or source_key]
    if source_host != instance_host:
        bits.append(source_host)
    bits.append(written_service or source_key)
    bits.extend(leaf)
    return "_".join(bits)


class ResolvedSecret:
    def __init__(self, podman: str, value: str, host: str, path: str) -> None:
        self.podman_name = podman
        self.value = value
        self.host = host
        self.path = path


def resolve_secret(
    ref: str,
    *,
    service: str,
    host: str,
    site: dict[str, dict[str, Any]],
    hosts: dict[str, dict[str, dict[str, Any]]],
) -> ResolvedSecret:
    """Resolve one secrets.* reference. `service` is the unit being rendered."""
    parts = [p for p in ref.split(".") if p]
    if parts and parts[0] == "secrets":
        parts = parts[1:]
    if not parts:
        raise SecretError("empty secret reference")
    if parts[0] == "site":
        return _resolve_site(parts[1:], site)
    if parts[0] == "hosts":
        if len(parts) < 4:
            raise SecretError(f"${{secrets.{'.'.join(parts)}}} needs a hostname, service, and secret name")
        return _resolve_host(
            parts[1], parts[2], parts[3:], hosts, consumer=service, instance_host=host, written=parts[2]
        )
    if parts[0] == "host":
        if not host:
            raise SecretError("${secrets.host.*} needs the instance host")
        rest = parts[1:]
        if len(rest) == 1:
            if not service:
                raise SecretError("${secrets.host.%s} needs the service being rendered" % rest[0])
            return _resolve_host(host, service, rest, hosts, consumer=service, instance_host=host, written=service)
        if rest[0] in hosts and len(rest) >= 3:
            return _resolve_host(
                rest[0], rest[1], rest[2:], hosts, consumer=service, instance_host=host, written=rest[1]
            )
        return _resolve_host(
            host, rest[0], rest[1:], hosts, consumer=service, instance_host=host, written=rest[0]
        )
    if len(parts) == 1:
        if not service:
            raise SecretError(f"${{secrets.{parts[0]}}} needs the service being rendered")
        return _resolve_site([service, parts[0]], site)
    return _resolve_site(parts, site)


def _resolve_site(parts: list[str], site: dict[str, dict[str, Any]]) -> ResolvedSecret:
    if len(parts) < 2:
        raise SecretError("a site secret needs a service and a secret name")
    found = _find_service(site, parts[0])
    if found is None:
        raise SecretError(f"secret secrets.site.{'.'.join(parts)} was not found")
    key, body = found
    value = _leaf(body, parts[1:])
    if value is None:
        raise SecretError(f"secret secrets.site.{key}.{'.'.join(parts[1:])} was not found")
    leaf = parts[1:]
    return ResolvedSecret(podman_name(key, leaf), value, "", f"secrets.site.{key}.{'.'.join(leaf)}")


def _resolve_host(
    hostname: str,
    service: str,
    leaf: list[str],
    hosts: dict[str, dict[str, dict[str, Any]]],
    *,
    consumer: str,
    instance_host: str,
    written: str,
) -> ResolvedSecret:
    if not leaf:
        raise SecretError(f"secrets.hosts.{hostname}.{service} needs a secret name")
    services = hosts.get(hostname)
    if services is None:
        raise SecretError(f"secret secrets.hosts.{hostname}.{service}.{'.'.join(leaf)} was not found")
    found = _find_service(services, service)
    if found is None:
        raise SecretError(f"secret secrets.hosts.{hostname}.{service}.{'.'.join(leaf)} was not found")
    key, body = found
    value = _leaf(body, leaf)
    if value is None:
        raise SecretError(f"secret secrets.hosts.{hostname}.{key}.{'.'.join(leaf)} was not found")
    return ResolvedSecret(
        _reference_name(consumer, key, hostname, instance_host, written, leaf),
        value,
        hostname,
        f"secrets.hosts.{hostname}.{key}.{'.'.join(leaf)}",
    )


def _leaves(body: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[tuple[list[str], str]]:
    out: list[tuple[list[str], str]] = []
    for key, val in body.items():
        path = prefix + (str(key),)
        if isinstance(val, dict):
            out.extend(_leaves(val, path))
        elif val is not None and not isinstance(val, list):
            out.append((list(path), str(val)))
    return out


def podman_catalog(data: dict[str, Any]) -> list[dict[str, str]]:
    """Site secrets (host "") and one entry per host secret. Colliding names on one host fail."""
    site, hosts = split_secrets(data)
    items: list[dict[str, str]] = []
    for service, body in site.items():
        for leaf, value in _leaves(body):
            items.append(
                {
                    "name": podman_name(service, leaf),
                    "value": value,
                    "host": "",
                    "key": f"secrets.site.{service}.{'.'.join(leaf)}",
                }
            )
    for hostname, services in hosts.items():
        for service, body in services.items():
            for leaf, value in _leaves(body):
                items.append(
                    {
                        "name": podman_name(service, leaf),
                        "value": value,
                        "host": hostname,
                        "key": f"secrets.hosts.{hostname}.{service}.{'.'.join(leaf)}",
                    }
                )
    for hostname in {item["host"] for item in items if item["host"]}:
        seen: dict[str, str] = {}
        for item in items:
            if item["host"] not in ("", hostname):
                continue
            prev = seen.get(item["name"])
            if prev is not None and prev != item["value"]:
                raise SecretError(f"host {hostname} would have two values for Podman secret {item['name']}")
            seen[item["name"]] = item["value"]
    return items


def reference_installs(desired: dict[str, Any], data: dict[str, Any], components: Path) -> list[dict[str, str]]:
    """Secrets named for the unit that references them, installed on that unit's host.

    A Pi-hole unit still installs pihole_web_password via podman_catalog. Homepage on Core
    also installs homepage_pi-hole_web_password (Core's value) and
    homepage_mantle_pi-hole_web_password (Mantle's value).
    """
    from .topology import all_services

    site, hosts = split_secrets(data)
    catalog = podman_catalog(data)
    items: list[dict[str, str]] = []
    seen: dict[tuple[str, str], str] = {}
    for svc in all_services(desired):
        host = str(svc.get("host") or "")
        service = str(svc.get("key") or "")
        comp = components / str(svc.get("component") or service)
        if not host or not comp.is_dir():
            continue
        for path in comp.rglob("*"):
            if not path.is_file() or path.name == "MANIFEST.toml":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"\$\{(secrets\.[^}]+)\}", text):
                resolved = resolve_secret(match.group(1), service=service, host=host, site=site, hosts=hosts)
                if _catalog_has(catalog, host, resolved.podman_name, resolved.value):
                    continue
                slot = (host, resolved.podman_name)
                prev = seen.get(slot)
                if prev is not None and prev != resolved.value:
                    raise SecretError(
                        f"host {host} would have two values for Podman secret {resolved.podman_name}"
                    )
                if prev is not None:
                    continue
                seen[slot] = resolved.value
                items.append(
                    {
                        "name": resolved.podman_name,
                        "value": resolved.value,
                        "host": host,
                        "key": resolved.path,
                    }
                )
    return items


def _catalog_has(items: list[dict[str, str]], install_host: str, name: str, value: str) -> bool:
    for item in items:
        if item["name"] != name or item["host"] not in ("", install_host):
            continue
        if item["value"] != value:
            raise SecretError(f"host {install_host} would have two values for Podman secret {name}")
        return True
    return False
