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

# Repo root path
def _repo() -> Path:
    return Path(os.environ.get("SITE_REPO", ROOT))

# Relative site.yaml path
def _desired_path(repo: Path) -> Path:
    return Path(os.environ.get("SITE_YAML", repo / "site.yaml"))

# Relative observed.yaml path
def _observed_path(repo: Path) -> Path:
    return Path(os.environ.get("OBSERVED_YAML", repo / "observed.yaml"))

# Relative ansible/inventory/hosts.yml path
def _inventory_path(repo: Path) -> Path:
    return repo / "ansible" / "inventory" / "hosts.yml"

# Relative ansible/.tmp path
def _tmp(repo: Path) -> Path:
    d = repo / "ansible" / ".tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d

# Relative secrets.yaml path
def _secrets_path(repo: Path, given: str | None) -> Path:
    path = Path(given) if given else repo / "secrets.yaml"
    if not path.is_absolute():
        path = repo / path
    return path

# Relative ansible/playbooks/<playbook> path
def _playbook(name: str) -> Path:
    return ANSIBLE / "playbooks" / name

# Execute Ansible playbook
def _ansible_playbook(playbook: Path, inventory: Path, extra: list[str] | None = None) -> int:
    cmd = ["ansible-playbook", "-i", str(inventory), str(playbook)]
    if extra:
        cmd.extend(extra)
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(ANSIBLE))

# Write plan.json
def _dump_plan(repo: Path, desired: dict) -> Path:
    plan_path = _tmp(repo) / "plan.json"
    plan_path.write_text(json.dumps(build_plan(desired), indent=2), encoding="utf-8")
    return plan_path

# Relative applied.json path
def _applied_path(repo: Path) -> Path:
    return repo / "applied.json"

# Calculate plan differences and write delta.json
def _dump_delta(repo: Path, desired: dict, observed_path: Path, secrets_path: Path, full: bool) -> Path:
    # Get last applied site config
    applied_path = _applied_path(repo)
    applied = None
    if applied_path.is_file() and not full:
        applied = json.loads(applied_path.read_text(encoding="utf-8"))

    # Treat an existing installation without applied state as an upgrade from observed state.
    upgrade = applied is None and observed_path.is_file() and not full

    # Calculate which configuration sections need applying
    delta = set_delta(
        desired,
        applied if isinstance(applied, dict) else None,
        secrets_path,
        full=full or (applied is None and not observed_path.is_file()),
        upgrade=upgrade,
    )

    # Calculate user-specific changes against observed state.
    if observed_path.is_file():
        import yaml

        observed = yaml.safe_load(observed_path.read_text()) or {}
        delta["users"] = user_delta(desired, observed)

    # Serialize the delta to JSON for consumption by the Ansible playbook.
    delta_path = _tmp(repo) / "delta.json"
    delta_path.write_text(json.dumps(delta), encoding="utf-8")

    # Print the configuration sections that will be processed.
    touched = [name for name, run in delta["sections"].items() if run]
    print("SET sections:", ", ".join(touched) if touched else "(none)", flush=True)
    return delta_path

# Parse "--hosts" arg from list of "<IP>, <user>" strings into hosts[('IP', '<user>')] list of pairs
def _parse_hosts(pairs: list[str]) -> list[tuple[str, str]]:
    out = []
    for raw in pairs:
        if "," not in raw:
            raise SystemExit(f"--host expects ip,user (got {raw})")
        ip, user = raw.split(",", 1)
        out.append((ip.strip(), user.strip()))
    return out

# GET command
def cmd_get(args: argparse.Namespace) -> int:
    # Repo paths
    repo = _repo()
    desired_path = _desired_path(repo)
    observed_path = _observed_path(repo)
    inventory_path = _inventory_path(repo)
    desired_exists = desired_path.is_file()

    # Get host IPs and users list from "--host" arg
    hosts = _parse_hosts(args.hosts or [])

    # Extra vars for Ansible when executing get.yml
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

    # Write inventory from site.yaml, if present
    if desired_exists:
        desired = load_desired(desired_path)
        write_inventory(desired, inventory_path)
        extra += ["-e", f"plan_json={_dump_plan(repo, desired)}"]
    # Else, write inventory from hosts IP and users list
    elif hosts:
        write_bootstrap_inventory(hosts, inventory_path)
        extra += ["-e", "print_scaffold=true"]
    # Else, request a site.yaml or "--host"s list 
    else:
        print("need site.yaml or --host ip,user for Day 0 GET", file=sys.stderr)
        return 2

    # Execute get.yml Ansible playbook
    rc = _ansible_playbook(_playbook("get.yml"), inventory_path, extra)
    
    # Print scaffold on "--scaffold" flag
    if rc == 0 and (args.scaffold or not desired_exists) and observed_path.is_file():
        import yaml

        observed = yaml.safe_load(observed_path.read_text()) or {}
        print(scaffold_desired(observed), end="")
        
        if desired_exists:
            print("# site.yaml unchanged", file=sys.stderr)

    return rc

# SET command
def cmd_set(args: argparse.Namespace) -> int:
    # Repo paths
    repo = _repo()
    desired_path = _desired_path(repo)
    secrets_path = _secrets_path(repo, args.secrets)

    # Validate site.yaml exists
    if not desired_path.is_file():
        print(f"missing desired site file: {desired_path}", file=sys.stderr)
        return 2
    
    # Validate secrets.yaml exists
    if not secrets_path.is_file():
        print(f"missing secrets file: {secrets_path}", file=sys.stderr)
        return 2

    # Get and validate site.yaml topology
    desired = load_desired(desired_path)
    errors = validate_placement(desired) + key_only_ready(desired)

    # Exit on site.yaml validation failure
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 2

    # Write hosts.yml inventory and plan.json plan
    write_inventory(desired, _inventory_path(repo))
    plan_path = _dump_plan(repo, desired)

    # Extra vars for Ansible when executing set.yml
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

    # Enable Ansible Check mode on "--check"
    if args.check:
        extra.append("--check")

    # Execute set.yml Ansible playbook
    return _ansible_playbook(_playbook("set.yml"), _inventory_path(repo), extra)

# APPLY command
def cmd_apply(args: argparse.Namespace) -> int:
    # Set args and run GET
    ns = argparse.Namespace(task="all", hosts=None, scaffold=False)
    rc = cmd_get(ns)

    # Exit if GET fails
    if rc != 0:
        return rc

    # Run SET
    return cmd_set(args)

# MAIN
def main() -> int:
    # Init "site" program (p) and "cmd" subcommand (sub)
    p = argparse.ArgumentParser(prog="site", description="Run GET or SET operation on the site.")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Init GET subcommand (g) and its "--task", "--host", and "--scaffold" args
    g = sub.add_parser("get", help="Read site facts (Task A) and site-influenced state (Task B) into observed.yaml")
    g.add_argument("--task", choices=["a", "b", "all"], default="all")
    g.add_argument(
        "--host",
        dest="hosts",
        action="append",
        help="Day 0 list of SSH target IPs and users to produce initial site.yaml",
    )
    g.add_argument("--scaffold", action="store_true", help="Print site scaffold without overwriting site.yaml)")
    g.set_defaults(func=cmd_get)

    # Init SET subcommand (s) and its "--secrets", "--check", and "--full" args
    s = sub.add_parser("set", help="Apply desired site.yaml (delta vs observed when present)")
    s.add_argument("--secrets", default=None, help="Path to secrets.yaml")
    s.add_argument("--check", action="store_true", help="Enable Ansible check mode")
    s.add_argument("--full", action="store_true", help="Run full SET plan, ignoring deltas")
    s.set_defaults(func=cmd_set)

    # Init APPLY subcommand (a) and its "--secrets", "--check", and "--full" args
    a = sub.add_parser("apply", help="Run GET then SET")
    a.add_argument("--secrets", default=None)
    a.add_argument("--check", action="store_true")
    a.add_argument("--full", action="store_true", help="Apply every section, ignoring the Day 2 delta")
    a.set_defaults(func=cmd_apply)

    # Parse program args and return functions
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
