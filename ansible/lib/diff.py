"""Desired versus observed delta for Day 2 SET."""
from __future__ import annotations

from typing import Any

from .topology import all_services, hosts, site_of


def _svc_key(s: dict[str, Any]) -> tuple[str, str]:
    return (s.get("host") or "", s.get("name") or s.get("key") or "")


def service_delta(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, list]:
    want = {_svc_key(s): s for s in all_services(desired)}
    have_list = ((observed.get("site") or {}).get("services") or observed.get("services") or [])
    have = {}
    if isinstance(have_list, list):
        for s in have_list:
            have[_svc_key(s)] = s
    elif isinstance(have_list, dict):
        for host, names in have_list.items():
            for n in names or []:
                have[(host, n)] = {"host": host, "name": n}
    add = [want[k] for k in want if k not in have]
    remove = [have[k] for k in have if k not in want]
    return {"add": add, "remove": remove}


def user_delta(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, list]:
    want = {u.get("name") for u in (site_of(desired).get("users") or []) if u.get("name")}
    obs_users = ((observed.get("site") or {}).get("users") or observed.get("users") or [])
    have = {u.get("name") for u in obs_users if isinstance(u, dict) and u.get("name")}
    return {"add": sorted(want - have), "remove": sorted(have - want)}


def host_names(desired: dict[str, Any]) -> list[str]:
    return [h.get("name") for h in hosts(desired) if h.get("name")]
