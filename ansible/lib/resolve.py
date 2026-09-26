"""Resolve ${site.*} ${host.*} ${secrets.*} and legacy ${DOMAIN}-style names."""
from __future__ import annotations

import re
from typing import Any

from .topology import env, ingress_host, root_owners, roots

VAR = re.compile(r"\$\{([^}]+)\}")
LOOPBACK = "169.254.1.2"


def _get_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def bind(desired: dict[str, Any], host: dict[str, Any] | None, secrets: dict[str, Any] | None) -> dict[str, str]:
    e = env(desired)
    owners = root_owners(desired)
    r = roots(desired)
    ing = ingress_host(desired) or {}
    host = host or {}
    secrets = secrets or {}
    out: dict[str, str] = {
        "site.env.domain": str(e.get("domain") or ""),
        "site.env.timezone": str(e.get("timezone") or "UTC"),
        "site.env.locale": str(e.get("locale") or "en_US.UTF-8"),
        "site.data.roots.appdata": r["appdata"],
        "site.data.roots.groups": r["groups"],
        "site.data.roots.users": r["users"],
        "site.networking.ingress.host.ip": str(ing.get("ip") or ""),
        "site.networking.ingress.host.name": str(ing.get("name") or ""),
        "host.name": str(host.get("name") or ""),
        "host.ip": str(host.get("ip") or ""),
        "SITE_HOST_LOOPBACK": LOOPBACK,
        "DOMAIN": str(e.get("domain") or ""),
        "TZ": str(e.get("timezone") or "UTC"),
        "NAS_LAN_IP": str(ing.get("ip") or ""),
        "NFS_USERS": r["users"],
        "NFS_SHARED": f"{r['groups']}/all",
        "DATA_ROOT": owners.get("appdata", {}).get("path") or r["appdata"],
        "PUID": "1000",
        "PGID": "1000",
        "HOMEPAGE_ALLOWED_HOSTS": ",".join(
            [
                f"dash.{e.get('domain') or 'example.lan'}",
                f"dash.{e.get('domain') or 'example.lan'}:8443",
                f"homepage.{e.get('domain') or 'example.lan'}",
            ]
        ),
        "PIHOLE_WEBPASSWORD": str(
            ((secrets.get("secrets") or secrets).get("pihole") or {}).get("web_password") or ""
        ),
        "HOMEPAGE_VAR_PIHOLE_TOKEN": str(
            ((secrets.get("secrets") or secrets).get("pihole") or {}).get("web_password") or ""
        ),
        "OPENCLOUD_ADMIN_PASSWORD": str(
            ((secrets.get("secrets") or secrets).get("opencloud") or {}).get("admin_password") or ""
        ),
        "NUT_REMOTE_PASSWORD": str(
            ((secrets.get("secrets") or secrets).get("peanut") or {}).get("nut_remote_password") or ""
        ),
        "WG_MTU": "1280",
    }
    wl = ((host.get("roles") or {}).get("workload") or {})
    if wl.get("user"):
        out["host.roles.workload.user"] = str(wl["user"])
    for gpu in (host.get("resources") or {}).get("gpu") or []:
        gid = gpu.get("id") or "gpu0"
        out[f"host.resources.gpu.{gid}"] = str(gpu.get("device") or "nvidia.com/gpu=all")
    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif node is not None and not isinstance(node, (list, dict)):
            out[prefix] = str(node)
    walk("secrets", secrets.get("secrets") or secrets)
    for root, owner in owners.items():
        out[f"site.data.roots.{root}.host"] = owner["host"]
        out[f"site.data.roots.{root}.ip"] = owner["host_ip"]
    return out


def render(text: str, mapping: dict[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in mapping:
            return mapping[key]
        # secrets.immich.database_password style already walked
        return m.group(0)

    return VAR.sub(repl, text)


def render_file(src: str, mapping: dict[str, str]) -> str:
    return render(src, mapping)


def unresolved(text: str) -> list[str]:
    return [m.group(1) for m in VAR.finditer(text) if not m.group(1).startswith("http")]
