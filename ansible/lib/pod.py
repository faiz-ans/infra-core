"""Merge a site.yaml pod overlay onto a catalog Pod. The catalog file stays a working baseline."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

NAMED_LISTS = {"containers", "initContainers", "volumes", "volumeMounts", "env"}


def merge_pod(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay wins for scalars. Named lists merge by name. Other mappings merge recursively."""
    out = copy.deepcopy(base)
    if not overlay:
        return out
    _merge_mapping(out, overlay)
    return out


def _merge_mapping(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, val in overlay.items():
        if key in NAMED_LISTS and isinstance(val, list):
            base[key] = _merge_named(base.get(key) or [], val)
        elif isinstance(val, dict) and isinstance(base.get(key), dict):
            _merge_mapping(base[key], val)
        else:
            base[key] = copy.deepcopy(val)


def _merge_named(base_items: list[Any], overlay_items: list[Any]) -> list[Any]:
    result: list[Any] = []
    index: dict[str, dict[str, Any]] = {}
    for item in base_items:
        copied = copy.deepcopy(item)
        result.append(copied)
        if isinstance(copied, dict) and copied.get("name"):
            index[str(copied["name"])] = copied
    for item in overlay_items:
        if isinstance(item, dict) and item.get("name") and str(item["name"]) in index:
            _merge_mapping(index[str(item["name"])], item)
            continue
        copied = copy.deepcopy(item)
        result.append(copied)
        if isinstance(copied, dict) and copied.get("name"):
            index[str(copied["name"])] = copied
    return result


_CONTAINER_KEYS = {
    "image",
    "pull",
    "environment",
    "volume",
    "addDevice",
    "podmanArgs",
    "publishPort",
    "secret",
}


def apply_container_overlay(text: str, overlay: dict[str, Any] | None) -> str:
    """Merge a site.yaml container: delta into one Quadlet .container unit."""
    if not overlay:
        return text
    unknown = set(overlay) - _CONTAINER_KEYS
    if unknown:
        raise ValueError(f"unknown container overlay keys: {', '.join(sorted(unknown))}")
    if overlay.get("image"):
        text = re.sub(r"^Image=.*$", f"Image={overlay['image']}", text, count=1, flags=re.M)
    if overlay.get("pull"):
        text = _upsert_line(text, "Pull=", f"Pull={overlay['pull']}")
    environment = overlay.get("environment") or {}
    if not isinstance(environment, dict):
        raise ValueError("container.environment must be a mapping")
    for name, value in environment.items():
        text = _upsert_line(text, f"Environment={name}=", f"Environment={name}={value}")
    for volume in overlay.get("volume") or []:
        text = _ensure_line(text, f"Volume={volume}")
    for device in overlay.get("addDevice") or []:
        text = _ensure_line(text, f"AddDevice={device}")
    for arg in overlay.get("podmanArgs") or []:
        text = _ensure_line(text, f"PodmanArgs={arg}")
    for port in overlay.get("publishPort") or []:
        text = _ensure_line(text, f"PublishPort={port}")
    for secret in overlay.get("secret") or []:
        text = _ensure_line(text, f"Secret={secret}")
    return text


def _ensure_line(text: str, line: str) -> str:
    if line in text.splitlines():
        return text
    return _insert_before_service(text, line)


def _upsert_line(text: str, prefix: str, line: str) -> str:
    pattern = re.compile(rf"^.*{re.escape(prefix)}.*$", re.M)
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return _insert_before_service(text, line)


def _insert_before_service(text: str, line: str) -> str:
    marker = "\n[Service]\n"
    if marker not in text:
        return text.rstrip() + "\n" + line + "\n"
    return text.replace(marker, "\n" + line + marker, 1)


def apply_pod_overlay(path: Path, overlay: dict[str, Any]) -> None:
    base = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(base, dict):
        raise ValueError(f"{path} is not a Pod mapping")
    merged = merge_pod(base, overlay)
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
