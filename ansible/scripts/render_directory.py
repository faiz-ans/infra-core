#!/usr/bin/env python3
"""Write SSSD config, OpenLDAP LDIF, and SMB password material for one host."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible"))

from lib.directory import (  # noqa: E402
    build_ldif,
    ldap_is_sot,
    render_sssd,
    require_admin_password,
    require_user_passwords,
)
from lib.secrets import SecretError, load_secrets  # noqa: E402
from lib.topology import load_desired, site_of  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    if len(sys.argv) < 5:
        print(
            "usage: render_directory.py DESIRED SECRETS OUTDIR HOST [--sssd-only|--accounts-only]",
            file=sys.stderr,
        )
        return 2
    desired = load_desired(Path(sys.argv[1]))
    secrets_path = Path(sys.argv[2])
    outdir = Path(sys.argv[3])
    host = sys.argv[4]
    mode = sys.argv[5] if len(sys.argv) > 5 else ""
    try:
        secrets = load_secrets(secrets_path) if secrets_path.is_file() else {}
        users = [user for user in (site_of(desired).get("users") or []) if user.get("name")]
        host_dir = outdir / host
        if mode == "--accounts-only":
            passwords = require_user_passwords(secrets, users)
            _write(
                host_dir / "accounts.json",
                json.dumps({"users": [{"name": name, "password": password} for name, password in passwords.items()]}),
            )
            return 0
        if not ldap_is_sot(desired):
            raise SecretError("identity.ldap is openldap but openldap is not placed")
        admin = require_admin_password(secrets)
        _write(host_dir / "sssd.conf", render_sssd(desired, host, admin))
        if mode == "--sssd-only":
            return 0
        passwords = require_user_passwords(secrets, users)
        add, modify = build_ldif(desired, passwords)
        _write(outdir / "add.ldif", add)
        _write(outdir / "modify.ldif", modify)
        _write(
            host_dir / "accounts.json",
            json.dumps({"users": [{"name": name, "password": password} for name, password in passwords.items()]}),
        )
    except SecretError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
