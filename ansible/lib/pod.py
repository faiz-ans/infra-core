"""Merge a site.yaml pod overlay onto a catalog Pod. The catalog file stays a working baseline."""
from __future__ import annotations

import copy
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


def apply_pod_overlay(path: Path, overlay: dict[str, Any]) -> None:
    base = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(base, dict):
        raise ValueError(f"{path} is not a Pod mapping")
    merged = merge_pod(base, overlay)
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
