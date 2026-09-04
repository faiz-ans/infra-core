#!/usr/bin/env python3
"""Build a Bitwarden/Vaultwarden JSON import from the catalog Caddyfile.

Each Caddy site block becomes one Login. Every host on that block is a URI
with match type Host (not Domain), so *.home.lan aliases do not steal
autofill from each other. Username and password are left empty — create
native accounts after import and fill them in the vault.

Redirect-only vhosts (gitea. → git.) are merged into the target login.

  DOMAIN=home.lan python3 bootstrap/vaultwarden-import.py -o vw-import.json

Vaultwarden → Tools → Import data → Bitwarden (json). Import once; a second
run creates duplicates.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

# Bitwarden UriMatchType.Host — not Domain (0). Domain match treats every
# https://*.home.lan URI as the same site.
URI_MATCH_HOST = 1
LOGIN_TYPE = 1

# Longest Caddy label → vault item name. Unlisted labels fall back to title case.
DISPLAY_NAMES = {
    "adventurelog": "Adventure Log",
    "authelia": "Authelia",
    "bentopdf": "BentoPDF",
    "bytestash": "ByteStash",
    "collabora": "Collabora",
    "frigate": "Frigate",
    "gitea": "Gitea",
    "glances-core": "Glances (Core)",
    "glances-periphery": "Glances (Periphery)",
    "grafana": "Grafana",
    "homeassistant": "Home Assistant",
    "homepage": "Homepage",
    "immich": "Immich",
    "it-tools": "IT Tools",
    "jellyseerr": "Jellyseerr",
    "jellyfin": "Jellyfin",
    "jotty": "Jotty",
    "komodo": "Komodo",
    "libretranslate": "LibreTranslate",
    "linkding": "Linkding",
    "n8n": "n8n",
    "opencloud": "OpenCloud",
    "openmediavault": "OpenMediaVault",
    "openreader": "OpenReader",
    "pihole-core": "Pi-hole (Core)",
    "pihole-periphery": "Pi-hole (Periphery)",
    "printer": "Printer",
    "prometheus": "Prometheus",
    "prowlarr": "Prowlarr",
    "qbittorrent": "qBittorrent",
    "radarr": "Radarr",
    "router": "Router",
    "rustdesk": "RustDesk",
    "scriberr": "Scriberr",
    "sonarr": "Sonarr",
    "transmute": "Transmute",
    "vaultwarden": "Vaultwarden",
    "wireguard": "WireGuard",
}

HOST_RE = re.compile(
    r"https://([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)\.\{\$DOMAIN\}"
)
REDIR_HOST_RE = re.compile(
    r"redir\s+https://([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)\.\{\$DOMAIN\}"
)


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def is_placeholder(text: str, i: int) -> bool:
    """Caddy {$ENV} / {host} / {http.reverse_proxy...} — not a block delimiter."""
    if text[i] != "{" or i + 1 >= len(text):
        return False
    nxt = text[i + 1]
    return nxt == "$" or nxt.isalpha() or nxt == "_"


def skip_placeholder(text: str, i: int) -> int:
    close = text.find("}", i + 1)
    if close < 0:
        raise ValueError("unbalanced placeholder in Caddyfile")
    return close + 1


def skip_brace_block(text: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        if is_placeholder(text, i):
            i = skip_placeholder(text, i)
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces in Caddyfile")



def iter_site_blocks(text: str) -> list[tuple[str, str]]:
    """Return (header, body) for each site block. Skip global {} and (snippets)."""
    blocks: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        if text[i] == "{":
            i = skip_brace_block(text, i)
            continue
        if text[i] == "(":
            close = text.find(")", i)
            if close < 0:
                raise ValueError("unbalanced snippet name in Caddyfile")
            i = close + 1
            while i < n and text[i].isspace():
                i += 1
            if i < n and text[i] == "{":
                i = skip_brace_block(text, i)
            continue
        start = i
        while i < n:
            if is_placeholder(text, i):
                i = skip_placeholder(text, i)
                continue
            if text[i] == "{":
                break
            i += 1
        if i >= n:
            break
        header = text[start:i].strip()
        body_open = i
        i = skip_brace_block(text, body_open)
        body = text[body_open + 1 : i - 1]
        blocks.append((header, body))
    return blocks


def hosts_from_header(header: str) -> list[str]:
    seen: list[str] = []
    for match in HOST_RE.finditer(header):
        label = match.group(1).lower()
        if label not in seen:
            seen.append(label)
    return seen


def is_host_redirect_only(body: str) -> str | None:
    """If the site only redirects to another vhost, return that vhost label."""
    target = REDIR_HOST_RE.search(body)
    if not target:
        return None
    if re.search(r"\breverse_proxy\b", body) or re.search(r"\brespond\b", body):
        return None
    return target.group(1).lower()


def canonical_label(hosts: list[str]) -> str:
    """Prefer the last host that has a display name (Caddy: aliases first, product last)."""
    for host in reversed(hosts):
        if host in DISPLAY_NAMES:
            return host
    return max(hosts, key=lambda h: (len(h), h))


def display_name(label: str) -> str:
    if label in DISPLAY_NAMES:
        return DISPLAY_NAMES[label]
    parts = label.replace("_", "-").split("-")
    titled = []
    for part in parts:
        if part.lower() == "n8n":
            titled.append("n8n")
        elif part.isupper() or part.lower() in ("it", "ha", "omv", "pdf"):
            titled.append(part.upper())
        else:
            titled.append(part.capitalize())
    return " ".join(titled)


def collect_logins(caddyfile: str) -> list[tuple[str, list[str]]]:
    sites: list[dict] = []
    for header, body in iter_site_blocks(caddyfile):
        hosts = hosts_from_header(header)
        if not hosts:
            continue
        sites.append(
            {
                "hosts": hosts,
                "redirect_to": is_host_redirect_only(body),
            }
        )

    by_host: dict[str, int] = {}
    for idx, site in enumerate(sites):
        for host in site["hosts"]:
            by_host[host] = idx

    drop: set[int] = set()
    for idx, site in enumerate(sites):
        target = site["redirect_to"]
        if not target:
            continue
        dest = by_host.get(target)
        if dest is None or dest == idx:
            continue
        for host in site["hosts"]:
            if host not in sites[dest]["hosts"]:
                sites[dest]["hosts"].append(host)
            by_host[host] = dest
        drop.add(idx)

    logins: list[tuple[str, list[str]]] = []
    seen_names: set[str] = set()
    for idx, site in enumerate(sites):
        if idx in drop:
            continue
        hosts = site["hosts"]
        name = display_name(canonical_label(hosts))
        if name in seen_names:
            raise ValueError(f"duplicate vault item name {name!r}")
        seen_names.add(name)
        logins.append((name, hosts))
    return logins


def bitwarden_export(domain: str, logins: list[tuple[str, list[str]]]) -> dict:
    folder_id = str(uuid.uuid4())
    items = []
    for name, hosts in logins:
        items.append(
            {
                "id": str(uuid.uuid4()),
                "organizationId": None,
                "folderId": folder_id,
                "type": LOGIN_TYPE,
                "reprompt": 0,
                "name": name,
                "notes": None,
                "favorite": False,
                "login": {
                    "uris": [
                        {
                            "match": URI_MATCH_HOST,
                            "uri": f"https://{host}.{domain}",
                        }
                        for host in hosts
                    ],
                    "username": "",
                    "password": "",
                    "totp": None,
                },
                "collectionIds": None,
            }
        )
    return {
        "encrypted": False,
        "folders": [{"id": folder_id, "name": domain}],
        "items": items,
    }


def default_caddyfile() -> Path:
    return Path(__file__).resolve().parent.parent / "stacks/platform/caddy/Caddyfile"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--caddyfile",
        type=Path,
        default=default_caddyfile(),
        help="Catalog Caddyfile (default: stacks/platform/caddy/Caddyfile)",
    )
    parser.add_argument(
        "--domain",
        default="",
        help="Public domain (default: $DOMAIN, else home.lan)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON here (default: stdout)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print item names and hosts; do not write JSON",
    )
    args = parser.parse_args()

    domain = (args.domain or os.environ.get("DOMAIN") or "home.lan").strip()
    if not domain:
        print("DOMAIN is empty", file=sys.stderr)
        return 1
    if not args.caddyfile.is_file():
        print(f"Caddyfile not found: {args.caddyfile}", file=sys.stderr)
        return 1

    text = strip_comments(args.caddyfile.read_text(encoding="utf-8"))
    logins = collect_logins(text)
    if not logins:
        print("No Caddy site blocks with {$DOMAIN} hosts", file=sys.stderr)
        return 1

    if args.list:
        for name, hosts in logins:
            urls = ", ".join(f"{h}.{domain}" for h in hosts)
            print(f"{name}: {urls}")
        return 0

    payload = bitwarden_export(domain, logins)
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(
            f"Wrote {len(logins)} logins to {args.output} "
            f"(folder {domain}, URI match Host)",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
