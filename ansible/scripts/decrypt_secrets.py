#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.secrets import flatten_secrets, load_secrets, podman_secret_names  # noqa: E402


def main() -> int:
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        dest.write_text("[]\n", encoding="utf-8")
        return 0
    items = podman_secret_names(flatten_secrets(load_secrets(src)))
    dest.write_text(json.dumps(items), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
