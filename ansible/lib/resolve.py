"""Resolve ${site.*} ${host.*} ${secrets.*} ${component.dir}. Secrets → Podman names."""
from __future__ import annotations

import re
from typing import Any

from .topology import env, ingress_host, policy, root_owners, roots

VAR = re.compile(r"\$\{([^}]+)\}")
LOOPBACK = "169.254.1.2"


def secret_name(path: str) -> str:
    """secrets.immich.database_password → immich_database_password."""
    key = path[8:] if path.startswith("secrets.") else path
    return key.replace(".", "_").replace("-", "_")


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
    wl = ((host.get("roles") or {}).get("workload") or {})
    out: dict[str, str] = {
        "site.env.domain": domain,
        "site.env.timezone": str(e.get("timezone") or "UTC"),
        "site.env.locale": str(e.get("locale") or "en_US.UTF-8"),
        "site.data.roots.appdata": r["appdata"],
        "site.data.roots.groups": r["groups"],
        "site.data.roots.users": r["users"],
        "site.networking.ingress.host.ip": str(ing.get("ip") or ""),
        "site.networking.ingress.host.name": str(ing.get("name") or ""),
        "site.networking.loopback": LOOPBACK,
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
        "host.name": str(host.get("name") or ""),
        "host.ip": str(host.get("ip") or ""),
        "host.roles.workload.user": str(wl.get("user") or ""),
        "host.roles.workload.uid": str(wl.get("uid") or "1000"),
        "host.roles.workload.gid": str(wl.get("gid") or "1000"),
    }
    for k, v in e.items():
        out[f"site.env.{k}"] = str(v)
    gpus = list((host.get("resources") or {}).get("gpu") or [])
    if not gpus:
        gpus = [{"id": "gpu0"}]
    for gpu in gpus:
        gid = gpu.get("id") or "gpu0"
        device = str(gpu.get("device") or "nvidia.com/gpu=all")
        resource = str(gpu.get("resource") or "nvidia.com/gpu")
        count = str(gpu.get("count") if gpu.get("count") is not None else 1)
        raw_vis = gpu.get("visible", True)
        if isinstance(raw_vis, str):
            visible = raw_vis.strip().lower() not in ("false", "0", "no", "off")
        else:
            visible = bool(raw_vis)
        out[f"host.resources.gpu.{gid}"] = device
        out[f"host.resources.gpu.{gid}.device"] = device
        out[f"host.resources.gpu.{gid}.resource"] = resource
        out[f"host.resources.gpu.{gid}.count"] = count
        out[f"host.resources.gpu.{gid}.visible"] = "all" if visible else "void"
    for root, owner in owners.items():
        out[f"site.data.roots.{root}.host"] = owner["host"]
        out[f"site.data.roots.{root}.ip"] = owner["host_ip"]
    return out


def render(text: str, mapping: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key.startswith("secrets."):
            return secret_name(key)
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
