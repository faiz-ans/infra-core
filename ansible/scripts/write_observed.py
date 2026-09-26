#!/usr/bin/env python3
"""Merge GET host facts into observed.yaml (stdin JSON)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.observed import write_observed  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: write_observed.py OBSERVED_PATH < facts.json", file=sys.stderr)
        return 2
    facts = json.load(sys.stdin)
    write_observed(Path(sys.argv[1]), facts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
