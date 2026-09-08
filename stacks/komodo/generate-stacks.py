#!/usr/bin/env python3
"""Generate ResourceSync TOML from topology.toml + fragments/.

Usage (from repo root):
  python3 stacks/komodo/generate-stacks.py

Writes:
  stacks/komodo/stacks-bootstrap.toml
  stacks/komodo/stacks-<server>.toml  (for each server with phase=full stacks)

Requires Python 3.9+. Uses stdlib only (minimal topology.toml parser).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOPOLOGY = ROOT / "topology.toml"
FRAGMENTS = ROOT / "fragments"

BOOTSTRAP_HEADER = """\
# GENERATED from topology.toml — do not hand-edit.
# Regenerate: python3 stacks/komodo/generate-stacks.py
#
# Phase A (bootstrap): identity, DNS, edge, OpenCloud (+ Collabora).
# May list stacks on multiple Komodo servers. Apply this ResourceSync path first
# on a greenfield site before stacks-core.toml / stacks-periphery.toml.
# Komodo does not interpolate [[VAR]] in server/repo — those must be literals.
# Environment [[VAR]] still interpolates at deploy from Core [secrets] / Variables.
# webhook_enabled is false; poll on-site.
# Stacks clone GitHub per stack (`repo`). ResourceSync uses topology linked_repo.

"""

CORE_HEADER = """\
# GENERATED from topology.toml — do not hand-edit.
# Regenerate: python3 stacks/komodo/generate-stacks.py
#
# Phase B stacks for server "core" (excludes bootstrap phase).
# Komodo does not interpolate [[VAR]] in server/repo — those must be literals.
# Environment [[VAR]] still interpolates at deploy from Core [secrets] / Variables.
# webhook_enabled is false; poll on-site.
# After Gitea is origin, set the Komodo Repo git provider to gitea:3000
# (HTTP). Core is dual-homed; compose default stays the internet gateway.

"""

PERIPHERY_HEADER = """\
# GENERATED from topology.toml — do not hand-edit.
# Regenerate: python3 stacks/komodo/generate-stacks.py
#
# Phase B stacks for server "periphery" (excludes bootstrap phase).
# Apply after the periphery server is connected.
# deploy = false in fragments: ResourceSync updates definitions without mass-starting.
# webhook_enabled is false; poll on-site.
# Storage: /config is always a local volume. Household data: compose.yaml +
# DATA_ROOT, or compose.nfs.yaml (this site). Do not list two transport files.
# Docker Desktop: bootstrap/periphery-docker-engine.ps1 before applying.

"""


def parse_topology(text: str) -> dict:
    """Minimal parser for topology.toml (servers list + [stacks.*] tables)."""
    servers: list[str] = []
    catalog: dict[str, str] = {}
    stacks: dict[str, dict] = {}
    current: str | None = None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r'^servers\s*=\s*\[(.*)\]\s*$', line)
        if m:
            servers = re.findall(r'"([^"]+)"', m.group(1))
            continue
        m = re.match(r'^\[stacks\.([^\]]+)\]\s*$', line)
        if m:
            current = m.group(1)
            stacks[current] = {}
            continue
        m = re.match(r'^(\w+)\s*=\s*"([^"]*)"\s*$', line)
        if m:
            key, value = m.group(1), m.group(2)
            if current is None:
                if key in ("repo", "branch", "linked_repo"):
                    catalog[key] = value
                continue
            stacks[current][key] = value
            continue
        m = re.match(r'^(\w+)\s*=\s*(true|false)\s*$', line)
        if m:
            if current is None:
                continue
            stacks[current][m.group(1)] = m.group(2) == "true"
            continue

    if not servers or not stacks:
        sys.exit("topology.toml must define servers and [stacks.*] tables")
    return {"servers": servers, "stacks": stacks, **catalog}


def load_topology() -> dict:
    return parse_topology(TOPOLOGY.read_text())


def fragment_for(name: str) -> str:
    path = FRAGMENTS / f"{name}.toml"
    if not path.is_file():
        sys.exit(f"missing fragment: {path}")
    return path.read_text()


def set_server(body: str, server: str) -> str:
    new, n = re.subn(
        r'^server\s*=\s*"[^"]*"',
        f'server = "{server}"',
        body,
        count=1,
        flags=re.M,
    )
    if n != 1:
        sys.exit(f"could not set server in fragment (replacements={n})")
    return new


def set_linked_repo(body: str, linked_repo: str) -> str:
    """Insert or replace linked_repo under [stack.config]. Empty clears it."""
    if not linked_repo:
        return re.sub(r'^linked_repo\s*=\s*"[^"]*"\n', "", body, flags=re.M)
    new, n = re.subn(
        r'^linked_repo\s*=\s*"[^"]*"',
        f'linked_repo = "{linked_repo}"',
        body,
        count=1,
        flags=re.M,
    )
    if n == 1:
        return new
    new, n = re.subn(
        r'^(repo\s*=\s*"[^"]*"\n)',
        rf'\1linked_repo = "{linked_repo}"\n',
        body,
        count=1,
        flags=re.M,
    )
    if n != 1:
        sys.exit(f"could not set linked_repo in fragment (replacements={n})")
    return new


def header_for(server: str | None, *, bootstrap: bool) -> str:
    if bootstrap:
        return BOOTSTRAP_HEADER
    if server == "core":
        return CORE_HEADER
    if server == "periphery":
        return PERIPHERY_HEADER
    return (
        "# GENERATED from topology.toml — do not hand-edit.\n"
        f"# Phase B stacks for server \"{server}\".\n"
        "# Regenerate: python3 stacks/komodo/generate-stacks.py\n\n"
    )


def emit(path: Path, header: str, names: list[str], topo: dict) -> None:
    stacks = topo["stacks"]
    linked_repo = topo.get("linked_repo", "")
    parts = [header]
    for name in names:
        meta = stacks[name]
        if meta.get("enabled", True) is False:
            continue
        body = set_server(fragment_for(name), meta["server"])
        # Opt-in: topology select_repo = true → linked_repo.
        select = meta.get("select_repo") is True
        body = set_linked_repo(body, linked_repo if select else "")
        parts.append(body.rstrip() + "\n\n")
    path.write_text("".join(parts).rstrip() + "\n")
    repo = ROOT.parent.parent
    print(f"wrote {path.relative_to(repo)} ({len(names)} stacks)")


def main() -> None:
    topo = load_topology()
    stacks = topo["stacks"]

    bootstrap: list[str] = []
    by_server: dict[str, list[str]] = {s: [] for s in topo["servers"]}

    for name, meta in stacks.items():
        if meta.get("enabled", True) is False:
            continue
        server = meta["server"]
        phase = meta["phase"]
        if phase == "bootstrap":
            bootstrap.append(name)
        elif phase == "full":
            by_server.setdefault(server, []).append(name)
        else:
            sys.exit(f"{name}: phase must be bootstrap or full, got {phase!r}")

    emit(ROOT / "stacks-bootstrap.toml", header_for(None, bootstrap=True), bootstrap, topo)
    for server, names in by_server.items():
        if not names:
            continue
        if server == "core":
            out = ROOT / "stacks-core.toml"
        elif server == "periphery":
            out = ROOT / "stacks-periphery.toml"
        else:
            out = ROOT / f"stacks-{server}.toml"
        emit(out, header_for(server, bootstrap=False), names, topo)


if __name__ == "__main__":
    main()
