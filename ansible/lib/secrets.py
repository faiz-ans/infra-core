"""Decrypt SOPS/Age on the runner. Never write a host site.env."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml


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
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data


def flatten_secrets(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else str(k), v)
        elif node is not None and not isinstance(node, list):
            out[prefix] = str(node)

    walk("", data.get("secrets") or data)
    return out


def podman_secret_names(flat: dict[str, str]) -> list[dict[str, str]]:
    """Map secrets.authelia.jwt → name authelia_jwt for `podman secret`."""
    items = []
    for key, value in flat.items():
        name = key.replace(".", "_").replace("-", "_")
        items.append({"name": name, "value": value, "key": key})
    return items
