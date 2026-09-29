#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.secrets import SecretError, load_secrets, podman_catalog, reference_installs  # noqa: E402
from lib.topology import load_desired  # noqa: E402


def main() -> int:
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    desired_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        dest.write_text("[]\n", encoding="utf-8")
        return 0
    try:
        data = load_secrets(src)
        items = podman_catalog(data)
        if desired_path and desired_path.is_file():
            items.extend(reference_installs(load_desired(desired_path), data, ROOT / "components"))
    except SecretError as exc:
        print(exc, file=sys.stderr)
        return 1
    dest.write_text(json.dumps(items), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
