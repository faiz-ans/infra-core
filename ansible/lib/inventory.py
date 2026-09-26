"""Write Ansible inventory from desired site.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .topology import hosts


def inventory_dict(desired: dict[str, Any]) -> dict[str, Any]:
    all_hosts: dict[str, Any] = {}
    storage: list[str] = []
    workload: list[str] = []
    for h in hosts(desired):
        name = h.get("name")
        if not name:
            continue
        roles = h.get("roles") or {}
        admin = next((u for u in (h.get("users") or []) if "sysadmin" in (u.get("roles") or [])), None)
        vars_ = {
            "ansible_host": h.get("ip"),
            "ansible_user": (admin or {}).get("name") or "root",
            "site_host_name": name,
            "site_host_ip": h.get("ip"),
        }
        if roles.get("storage"):
            storage.append(name)
            vars_["site_role_storage"] = True
        if roles.get("workload"):
            workload.append(name)
            vars_["site_role_workload"] = True
            wl = roles["workload"] if isinstance(roles["workload"], dict) else {}
            if wl.get("user"):
                vars_["site_workload_user"] = wl["user"]
        all_hosts[name] = vars_
    return {
        "all": {
            "hosts": all_hosts,
            "children": {
                "storage": {"hosts": {n: {} for n in storage}},
                "workload": {"hosts": {n: {} for n in workload}},
            },
        }
    }


def write_inventory(desired: dict[str, Any], dest: Path) -> Path:
    import yaml

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(inventory_dict(desired), sort_keys=False), encoding="utf-8")
    return dest


def write_bootstrap_inventory(pairs: list[tuple[str, str]], dest: Path) -> Path:
    """Day 0: IPs + admin usernames only."""
    import yaml

    hosts = {}
    for i, (ip, user) in enumerate(pairs):
        name = f"host{i}"
        hosts[name] = {
            "ansible_host": ip,
            "ansible_user": user,
            "site_host_name": name,
            "site_host_ip": ip,
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.safe_dump({"all": {"hosts": hosts}}, sort_keys=False),
        encoding="utf-8",
    )
    return dest
