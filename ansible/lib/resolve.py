"""Resolve ${site.*} ${host.*} ${secrets.*} ${component.dir}. Secrets → Podman names."""
from __future__ import annotations

import re
from typing import Any

from .secrets import resolve_secret, split_secrets
from .topology import env, host_roots, hosts, ingress_host, policy, root_owners, roots

VAR = re.compile(r"\$\{([^}]+)\}")
LOOPBACK = "169.254.1.2"


def secret_name(path: str) -> str:
    """Name-only fallback when no secrets file is loaded. secrets.immich.database_password → immich_database_password."""
    key = path[8:] if path.startswith("secrets.") else path
    return key.replace(".", "_").replace("-", "_")


def _publish_host(out: dict[str, str], prefix: str, host: dict[str, Any]) -> None:
    """Publish one host's fields. prefix is `host.` or `site.hosts.<name>.`."""
    wl = ((host.get("operations") or {}).get("workload") or {})
    out[f"{prefix}name"] = str(host.get("name") or "")
    out[f"{prefix}ip"] = str(host.get("ip") or "")
    out[f"{prefix}operations.workload.user"] = str(wl.get("user") or "")
    out[f"{prefix}operations.workload.uid"] = str(wl.get("uid") or "1000")
    out[f"{prefix}operations.workload.gid"] = str(wl.get("gid") or "1000")
    for k, v in (host.get("env") or {}).items():
        out[f"{prefix}env.{k}"] = str(v)
    for gpu in list((host.get("resources") or {}).get("gpu") or []):
        gid = str(gpu.get("id") or "").strip()
        if not gid:
            continue
        out[f"{prefix}resources.gpu.{gid}.id"] = gid
        out[f"{prefix}resources.gpu.{gid}.name"] = str(gpu.get("name") or "")
        out[f"{prefix}resources.gpu.{gid}.uuid"] = str(gpu.get("uuid") or "")
        out[f"{prefix}resources.gpu.{gid}.resource"] = str(gpu.get("resource") or "nvidia.com/gpu")
    for root, path in host_roots(host).items():
        out[f"{prefix}data.roots.{root}"] = path


def bind(desired: dict[str, Any], host: dict[str, Any] | None, secrets: dict[str, Any] | None = None) -> dict[str, str]:
    """Build the substitution map. Secret keys are names only; values are unused."""
    del secrets  # names come from ${secrets.*} paths in render()
    e = env(desired)
    owners = root_owners(desired)
    r = roots(desired)
    ing = ingress_host(desired) or {}
    host = host or {}
    p = policy(desired)
    domain = str(e.get("domain") or "")
    out: dict[str, str] = {
        "site.env.domain": domain,
        "site.env.timezone": str(e.get("timezone") or "UTC"),
        "site.env.locale": str(e.get("locale") or "en_US.UTF-8"),
        "site.data.roots.appdata": r["appdata"],
        "site.data.roots.groups": r["groups"],
        "site.data.roots.users": r["users"],
        "site.networking.ingress.host.ip": str(ing.get("ip") or ""),
        "site.networking.ingress.host.name": str(ing.get("name") or ""),
        "host-loopback-mapped-ip": LOOPBACK,
        "site.networking.tunnel.endpoint": str(p.get("tunnel_endpoint") or ""),
        "site.homepage.allowed_hosts": ",".join(
            [
                f"dash.{domain}",
                f"dash.{domain}:8443",
                f"homepage.{domain}",
            ]
        )
        if domain
        else "",
    }
    for k, v in e.items():
        out[f"site.env.{k}"] = str(v)
    _publish_host(out, "host.", host)
    # Service state follows the host. A storage host with no local root uses the site appdata it mounts.
    out["host.appdata"] = host_roots(host).get("appdata") or r["appdata"]
    for other in hosts(desired):
        name = str(other.get("name") or "")
        if name:
            _publish_host(out, f"site.hosts.{name}.", other)
    for root, owner in owners.items():
        out[f"site.data.roots.{root}.host"] = owner["host"]
        out[f"site.data.roots.{root}.ip"] = owner["host_ip"]
    return out


def render(
    text: str,
    mapping: dict[str, str],
    *,
    service: str = "",
    host: str = "",
    secrets: dict[str, Any] | None = None,
) -> str:
    site: dict[str, Any] = {}
    hosts: dict[str, Any] = {}
    if secrets is not None:
        site, hosts = split_secrets(secrets)

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key.startswith("secrets."):
            if secrets is None:
                return secret_name(key)
            return resolve_secret(key, service=service, host=host, site=site, hosts=hosts).podman_name
        if key in mapping:
            return mapping[key]
        return m.group(0)

    return VAR.sub(repl, text)


def render_file(src: str, mapping: dict[str, str]) -> str:
    return render(src, mapping)


def unresolved(text: str) -> list[str]:
    out = []
    for m in VAR.finditer(text):
        key = m.group(1)
        if key.startswith("secrets.") or key.startswith("http"):
            continue
        out.append(key)
    return out
