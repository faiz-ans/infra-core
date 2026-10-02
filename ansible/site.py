#!/usr/bin/env python3
"""Operator CLI: get (facts), set (apply desired), apply (get then set)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = Path(__file__).resolve().parent
sys.path.insert(0, str(ANSIBLE))

from lib.diff import set_delta, user_delta  # noqa: E402
from lib.inventory import write_bootstrap_inventory, write_inventory  # noqa: E402
from lib.observed import scaffold_desired  # noqa: E402
from lib.plan import build_plan  # noqa: E402
from lib.topology import key_only_ready, load_desired, validate_placement  # noqa: E402


def _repo() -> Path:
    return Path(os.environ.get("SITE_REPO", ROOT))


def _desired_path(repo: Path) -> Path:
    return Path(os.environ.get("SITE_YAML", repo / "site.yaml"))


def _observed_path(repo: Path) -> Path:
    return Path(os.environ.get("OBSERVED_YAML", repo / "observed.yaml"))


def _inventory_path(repo: Path) -> Path:
    return repo / "ansible" / "inventory" / "hosts.yml"


def _tmp(repo: Path) -> Path:
    d = repo / "ansible" / ".tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _secrets_path(repo: Path, given: str | None) -> Path:
    path = Path(given) if given else repo / "secrets.yaml"
    if not path.is_absolute():
        path = repo / path
    return path


def _playbook(name: str) -> Path:
    return ANSIBLE / "playbooks" / name


def _ansible_playbook(playbook: Path, inventory: Path, extra: list[str] | None = None) -> int:
    cmd = ["ansible-playbook", "-i", str(inventory), str(playbook)]
    if extra:
        cmd.extend(extra)
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(ANSIBLE))


def _dump_plan(repo: Path, desired: dict) -> Path:
    plan_path = _tmp(repo) / "plan.json"
    plan_path.write_text(json.dumps(build_plan(desired), indent=2), encoding="utf-8")
    return plan_path


def _applied_path(repo: Path) -> Path:
    return repo / "applied.json"


def _dump_delta(repo: Path, desired: dict, observed_path: Path, secrets_path: Path, full: bool) -> Path:
    """Write the Day 2 delta as a file. Inline -e JSON is split on spaces by Ansible."""
    applied_path = _applied_path(repo)
    applied = None
    if applied_path.is_file() and not full:
        applied = json.loads(applied_path.read_text(encoding="utf-8"))
    upgrade = applied is None and observed_path.is_file() and not full
    delta = set_delta(
        desired,
        applied if isinstance(applied, dict) else None,
        secrets_path,
        full=full or (applied is None and not observed_path.is_file()),
        upgrade=upgrade,
    )
    if observed_path.is_file():
        import yaml

        observed = yaml.safe_load(observed_path.read_text()) or {}
        delta["users"] = user_delta(desired, observed)
    delta_path = _tmp(repo) / "delta.json"
    delta_path.write_text(json.dumps(delta), encoding="utf-8")
    touched = [name for name, run in delta["sections"].items() if run]
    print("SET sections:", ", ".join(touched) if touched else "(none)", flush=True)
    return delta_path


def _parse_hosts(pairs: list[str]) -> list[tuple[str, str]]:
    out = []
    for raw in pairs:
        if "," not in raw:
            raise SystemExit(f"--host expects ip,user (got {raw})")
        ip, user = raw.split(",", 1)
        out.append((ip.strip(), user.strip()))
    return out


def cmd_get(args: argparse.Namespace) -> int:
    repo = _repo()
    desired_path = _desired_path(repo)
    observed_path = _observed_path(repo)
    hosts = _parse_hosts(args.hosts or [])
    extra = [
        "-e",
        f"site_repo={repo}",
        "-e",
        f"desired_path={desired_path}",
        "-e",
        f"observed_path={observed_path}",
        "-e",
        f"get_task={args.task}",
        "-e",
        f"print_scaffold={str(args.scaffold).lower()}",
    ]
    if desired_path.is_file():
        desired = load_desired(desired_path)
        write_inventory(desired, _inventory_path(repo))
        extra += ["-e", f"plan_json={_dump_plan(repo, desired)}"]
    elif hosts:
        write_bootstrap_inventory(hosts, _inventory_path(repo))
        extra += ["-e", "print_scaffold=true"]
    else:
        print("need site.yaml or --host ip,user for Day 0 GET", file=sys.stderr)
        return 2
    rc = _ansible_playbook(_playbook("get.yml"), _inventory_path(repo), extra)
    if rc == 0 and (args.scaffold or not desired_path.is_file()) and observed_path.is_file():
        import yaml

        observed = yaml.safe_load(observed_path.read_text()) or {}
        print(scaffold_desired(observed), end="")
        if desired_path.is_file():
            print("# existing site.yaml left untouched", file=sys.stderr)
    return rc


def cmd_set(args: argparse.Namespace) -> int:
    repo = _repo()
    desired_path = _desired_path(repo)
    if not desired_path.is_file():
        print(f"missing desired site file: {desired_path}", file=sys.stderr)
        return 2
    desired = load_desired(desired_path)
    errors = validate_placement(desired) + key_only_ready(desired)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 2
    secrets_path = _secrets_path(repo, args.secrets)
    if not secrets_path.is_file():
        print(f"missing secrets file: {secrets_path}", file=sys.stderr)
        return 2
    write_inventory(desired, _inventory_path(repo))
    plan_path = _dump_plan(repo, desired)
    extra = [
        "-e",
        f"site_repo={repo}",
        "-e",
        f"desired_path={desired_path}",
        "-e",
        f"observed_path={_observed_path(repo)}",
        "-e",
        f"secrets_file={secrets_path}",
        "-e",
        f"plan_json={plan_path}",
        "-e",
        f"delta_path={_dump_delta(repo, desired, _observed_path(repo), secrets_path, args.full)}",
        "-e",
        f"applied_path={_applied_path(repo)}",
    ]
    if args.check:
        extra.append("--check")
    return _ansible_playbook(_playbook("set.yml"), _inventory_path(repo), extra)


def cmd_apply(args: argparse.Namespace) -> int:
    ns = argparse.Namespace(task="all", hosts=None, scaffold=False)
    rc = cmd_get(ns)
    if rc != 0:
        return rc
    return cmd_set(args)


def main() -> int:
    p = argparse.ArgumentParser(prog="site", description="Site GET/SET from the operator machine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get", help="Read facts (A) and site-influenced state (B) into observed.yaml")
    g.add_argument("--task", choices=["a", "b", "all"], default="all")
    g.add_argument(
        "--host",
        dest="hosts",
        action="append",
        help="Day 0 SSH target ip,user (repeatable). Used when site.yaml is absent.",
    )
    g.add_argument("--scaffold", action="store_true", help="Print a new-desired scaffold; never overwrite site.yaml")
    g.set_defaults(func=cmd_get)

    s = sub.add_parser("set", help="Apply desired site.yaml (delta vs observed when present)")
    s.add_argument("--secrets", default=None, help="Path to SOPS-encrypted secrets.yaml")
    s.add_argument("--check", action="store_true", help="Ansible check mode")
    s.add_argument("--full", action="store_true", help="Apply every section, ignoring the Day 2 delta")
    s.set_defaults(func=cmd_set)

    a = sub.add_parser("apply", help="GET then SET")
    a.add_argument("--secrets", default=None)
    a.add_argument("--check", action="store_true")
    a.add_argument("--full", action="store_true", help="Apply every section, ignoring the Day 2 delta")
    a.set_defaults(func=cmd_apply)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
