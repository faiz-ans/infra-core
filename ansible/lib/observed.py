"""Write observed.yaml from GET facts. Never overwrite an existing desired file."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def merge_observed(host_facts: list[dict[str, Any]]) -> dict[str, Any]:
    hosts_out = []
    services: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    for hf in host_facts:
        census = hf.get("census") or {}
        state = hf.get("state") or {}
        name = hf.get("name") or census.get("hostname") or ""
        hosts_out.append(
            {
                "name": name,
                "ip": hf.get("ip") or census.get("ip") or "",
                "mac": census.get("mac") or "",
                "os": census.get("os") or {},
                "timezone": census.get("timezone") or "",
                "locale": census.get("locale") or "",
                "disks": census.get("disks") or [],
                "gpus": census.get("gpus") or [],
                "ups": census.get("ups") or [],
                "pwm": census.get("pwm") or "",
                "unix_users": census.get("users") or [],
                "mounts": state.get("mounts") or [],
                "nfs_exports": state.get("nfs_exports") or "",
                "smb": state.get("smb"),
                "cockpit": state.get("cockpit"),
                "podman": state.get("podman"),
                "containers": state.get("containers") or [],
                "ldap": state.get("ldap") or {},
            }
        )
        for c in state.get("containers") or []:
            if isinstance(c, str):
                services.append({"host": name, "name": c})
            elif isinstance(c, dict):
                services.append({"host": name, "name": c.get("name") or c.get("Names")})
        for u in census.get("users") or []:
            if isinstance(u, dict) and u.get("name"):
                users.append({"name": u["name"], "uid": u.get("uid"), "gid": u.get("gid"), "host": name})
    return {
        "observed": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hosts": hosts_out,
        },
        "services": services,
        "users": users,
    }


def write_observed(path: Path, host_facts: list[dict[str, Any]]) -> Path:
    path.write_text(yaml.safe_dump(merge_observed(host_facts), sort_keys=False), encoding="utf-8")
    return path


def scaffold_desired(observed: dict[str, Any]) -> str:
    """Print-only scaffold. Caller must not write this over an existing site.yaml."""
    hosts = (observed.get("observed") or observed).get("hosts") or []
    lines = [
        "# Scaffold from GET A. Copy to site.yaml and edit. Do not commit.",
        "site:",
        "  data:",
        "    roots: { appdata: /appdata, groups: /groups, users: /users }",
        "    access: { filesystem: smb, web: none }",
        "  networking: { dns: none, ingress: none }",
        "  identity: { ldap: none, sso: none, ssh: false }",
        "  operations:",
        "    host: { manager: cockpit, monitor: glances }",
        "    storage: { engine: native, monitor: none }",
        "    workload: { engine: podman, monitor: none }",
        "  env: { domain: example.lan, timezone: UTC, locale: en_US.UTF-8 }",
        "  users: []",
        "  hosts:",
    ]
    for h in hosts:
        osinfo = h.get("os") or {}
        lines += [
            f"    - name: {h.get('name') or 'host'}",
            f"      ip: {h.get('ip') or '10.0.0.10'}",
            f"      mac: {h.get('mac') or ''}",
            f"      os: {{ name: {str(osinfo.get('name') or 'debian').lower()}, version: \"{osinfo.get('version') or ''}\" }}",
            "      users:",
            "        - name: admin",
            "          roles: [sysadmin]",
            "          ssh-keys: []",
            "      roles: {}",
        ]
        disks = h.get("disks") or []
        if disks:
            lines.append("      resources:")
            lines.append("        disks:")
            for d in disks:
                uuid = d.get("uuid") or d.get("UUID") or ""
                ident = d.get("name") or d.get("kname") or d.get("id") or "disk"
                lines.append(f"          - id: {ident}")
                if uuid:
                    lines.append(f"            uuid: {uuid}")
    return "\n".join(lines) + "\n"
