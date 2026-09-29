#!/usr/bin/env python3
"""Write Caddyfile, Authelia, Homepage from desired + pack into ansible/.tmp/edge/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.generate import (  # noqa: E402
    generate_authelia,
    generate_authelia_users,
    generate_caddyfile,
    generate_homepage_services,
)
from lib.topology import load_desired, policy  # noqa: E402


def main() -> int:
    desired = load_desired(Path(sys.argv[1]))
    dest = Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    p = policy(desired)
    if p["generate_upstream"]:
        (dest / "Caddyfile").write_text(generate_caddyfile(desired), encoding="utf-8")
        (dest / "configuration.yml").write_text(generate_authelia(desired), encoding="utf-8")
        (dest / "users.yml").write_text(generate_authelia_users(desired), encoding="utf-8")
    if p["generate_tiles"]:
        (dest / "services.yaml").write_text(generate_homepage_services(desired), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
