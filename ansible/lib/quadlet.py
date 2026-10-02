"""Strip Kubernetes-only fields; keep kube-play Pod YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

KEEP_KINDS = {"Pod", "ConfigMap", "Secret", "PersistentVolumeClaim"}
DROP_POD_FIELDS = (
    "serviceAccountName",
    "serviceAccount",
    "nodeSelector",
    "tolerations",
    "affinity",
    "topologySpreadConstraints",
    "priorityClassName",
    "schedulerName",
    "preemptionPolicy",
    "runtimeClassName",
)


def strip_doc(doc: Any) -> Any | None:
    if not isinstance(doc, dict):
        return doc
    kind = doc.get("kind")
    if kind and kind not in KEEP_KINDS:
        return None
    meta = doc.get("metadata")
    if isinstance(meta, dict):
        meta.pop("namespace", None)
        meta.pop("uid", None)
        meta.pop("resourceVersion", None)
        meta.pop("generation", None)
        meta.pop("managedFields", None)
        meta.pop("ownerReferences", None)
    spec = doc.get("spec")
    if isinstance(spec, dict):
        for k in DROP_POD_FIELDS:
            spec.pop(k, None)
    return doc


def strip_yaml_text(text: str) -> str:
    docs = list(yaml.safe_load_all(text))
    kept = []
    for d in docs:
        s = strip_doc(d)
        if s is not None:
            kept.append(s)
    if not kept:
        return ""
    return yaml.safe_dump_all(kept, sort_keys=False)


def read_utf8(path: Path) -> str | None:
    """Text for ${} substitution. None leaves a binary file (a background image) unchanged."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def privilege_tree(privilege: str) -> str:
    """Relative install tree. Rootful = system; rootless = workload user."""
    if privilege == "rootful":
        return "/etc/containers/systemd"
    return "~/.config/containers/systemd"
