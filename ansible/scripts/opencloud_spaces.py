#!/usr/bin/env python3
"""Stamp OpenCloud personal and group spaces. Prints `scan <container path>` when a root changed."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.opencloud_spaces import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
