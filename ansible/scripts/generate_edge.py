#!/usr/bin/env python3
"""Write Caddyfile, Authelia, Homepage from desired + pack into ansible/.tmp/edge/."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.directory import file_backend_needs_passwords, require_user_passwords  # noqa: E402
from lib.generate import (  # noqa: E402
    generate_authelia,
    generate_authelia_users,
    generate_caddyfile,
)
from lib.secrets import SecretError, load_secrets  # noqa: E402
from lib.topology import load_desired, policy, site_of  # noqa: E402


def _passwords(desired: dict, secrets_path: Path) -> dict[str, str]:
    if not secrets_path.is_file():
        if file_backend_needs_passwords(desired):
            raise SecretError("site users need secrets.site.users.<name>.password")
        return {}
    secrets = load_secrets(secrets_path)
    users = [user for user in (site_of(desired).get("users") or []) if user.get("name")]
    if file_backend_needs_passwords(desired):
        return require_user_passwords(secrets, users)
    try:
        return require_user_passwords(secrets, users)
    except SecretError:
        return {}


def main() -> int:
    desired = load_desired(Path(sys.argv[1]))
    dest = Path(sys.argv[2])
    secrets_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path()
    dest.mkdir(parents=True, exist_ok=True)
    p = policy(desired)
    if p["generate_upstream"]:
        (dest / "Caddyfile").write_text(generate_caddyfile(desired), encoding="utf-8")
        (dest / "configuration.yml").write_text(generate_authelia(desired), encoding="utf-8")
        try:
            users = generate_authelia_users(desired, _passwords(desired, secrets_path))
        except SecretError as exc:
            print(exc, file=sys.stderr)
            return 1
        (dest / "users.yml").write_text(users, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
