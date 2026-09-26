"""Generate Caddyfile, Authelia, and Homepage config from desired + pack."""
from __future__ import annotations

from typing import Any

from .resolve import LOOPBACK
from .topology import all_services, env, policy, site_of


def domain_of(desired: dict[str, Any]) -> str:
    return str(env(desired).get("domain") or "example.lan")


def generate_caddyfile(desired: dict[str, Any]) -> str:
    domain = domain_of(desired)
    lines = [
        "{",
        "	email off",
        "	http_port 8080",
        "	https_port 8443",
        "	servers {",
        "		protocols h1 h2",
        "	}",
        "	admin 0.0.0.0:2019 {",
        f"		origins caddy:2019 caddy 127.0.0.1:2019 localhost:2019 {LOOPBACK}:2019",
        "	}",
        "}",
        "",
        "(authelia_gate) {",
        "	forward_auth 127.0.0.1:9091 {",
        f"		uri /api/authz/forward-auth?authelia_url=https://auth.{domain}/",
        "		copy_headers Remote-User Remote-Groups Remote-Name Remote-Email",
        "	}",
        "}",
        "",
    ]
    seen = set()
    for s in all_services(desired):
        sub = s.get("subdomain") or {}
        primary = sub.get("primary")
        if not primary or primary in seen:
            continue
        seen.add(primary)
        aliases = sub.get("aliases") or []
        names = [f"https://{primary}.{domain}"] + [f"https://{a}.{domain}" for a in aliases]
        if aliases:
            for a in aliases:
                lines += [
                    f"https://{a}.{domain} {{",
                    "	tls internal",
                    f"	redir https://{primary}.{domain}{{uri}} permanent",
                    "}",
                    "",
                ]
        sso = s.get("sso") or "none"
        port = (s.get("ports") or {}).get("web") or (s.get("publish") or [""])
        # publish like 127.0.0.1:9200:9200
        upstream = "127.0.0.1"
        up_port = None
        if s.get("publish"):
            parts = s["publish"][0].split(":")
            if len(parts) >= 3:
                up_port = parts[-1]
            elif len(parts) == 2:
                up_port = parts[-1]
        if (s.get("ports") or {}).get("https"):
            up_port = up_port or "8443"
        if (s.get("ports") or {}).get("web"):
            up_port = str(s["ports"]["web"])
        if s["key"] == "caddy":
            continue
        if s["key"] == "authelia":
            up_port = "9091"
        if s["key"] == "opencloud":
            up_port = "9200"
        if s["key"] == "homepage":
            up_port = "3000"
        if s["key"] == "pi-hole":
            up_port = str((s.get("ports") or {}).get("web") or 8088)
        if not up_port:
            continue
        lines += [f"https://{primary}.{domain} {{", "	tls internal"]
        if sso == "forward-auth":
            lines.append("	import authelia_gate")
        if sso == "admin-only":
            lines += [
                "	handle /admin* {",
                "		import authelia_gate",
                f"		reverse_proxy {upstream}:{up_port}",
                "	}",
            ]
        lines += [
            f"	reverse_proxy {upstream}:{up_port} {{",
            f"		header_up Host {primary}.{domain}",
            f"		header_up X-Forwarded-Host {primary}.{domain}",
            "		header_up X-Forwarded-Proto https",
            "	}",
            "}",
            "",
        ]
    return "\n".join(lines)


def generate_authelia(desired: dict[str, Any]) -> str:
    domain = domain_of(desired)
    p = policy(desired)
    backend = "ldap" if p["ldap"] == "openldap" else "file"
    if backend == "file":
        auth = [
            "authentication_backend:",
            "  file:",
            "    path: /config/userdb/users.yml",
            "    watch: true",
        ]
    else:
        auth = [
            "authentication_backend:",
            "  ldap:",
            "    implementation: custom",
            "    address: ldap://openldap:389",
            "    timeout: 5s",
            "    start_tls: false",
            "    base_dn: dc=site,dc=lan",
            "    user: cn=admin,dc=site,dc=lan",
            "    password: '{{ env \"LDAP_ADMIN_PASSWORD\" }}'",
            "    attributes:",
            "      username: uid",
            "      display_name: cn",
            "      mail: mail",
            "      group_name: cn",
        ]
    clients: list[str] = []
    for s in all_services(desired):
        if s.get("sso") != "oidc":
            continue
        sub = (s.get("subdomain") or {}).get("primary") or s["name"]
        clients += [
            f"      - client_id: {s['key']}",
            f"        client_name: {s['name']}",
            "        public: true",
            "        authorization_policy: one_factor",
            "        scopes: [openid, groups, profile, email]",
            f"        redirect_uris: ['https://{sub}.{domain}/', 'https://{sub}.{domain}/oidc-callback.html']",
            "        token_endpoint_auth_method: none",
        ]
        if s["key"] == "opencloud":
            clients.append("        claims_policy: opencloud")
    if not clients:
        clients = ["      []"]
    return "\n".join(
        [
            "server:",
            "  address: tcp://0.0.0.0:9091",
            *auth,
            "access_control:",
            "  default_policy: deny",
            "  rules:",
            f"    - domain: 'auth.{domain}'",
            "      policy: bypass",
            "session:",
            f"  domain: {domain}",
            "identity_providers:",
            "  oidc:",
            "    claims_policies:",
            "      opencloud:",
            "        id_token: [email, email_verified, preferred_username, name, groups]",
            "    clients:",
            *clients,
            "",
        ]
    )


def generate_authelia_users(desired: dict[str, Any]) -> str:
    """File-backend users.yml (passwords filled later / by secrets)."""
    lines = ["users:"]
    for u in site_of(desired).get("users") or []:
        name = u.get("name")
        roles = u.get("roles") or []
        groups = ["users"]
        if "appadmin" in roles:
            groups.append("admins")
        groups.extend(u.get("groups") or [])
        lines += [
            f"  {name}:",
            f"    displayname: {u.get('displayname') or name}",
            f"    email: {u.get('email') or name + '@' + domain_of(desired)}",
            "    password: '{{ secrets_user_hash }}'",
            f"    groups: {groups}",
        ]
    return "\n".join(lines)


def generate_homepage_services(desired: dict[str, Any]) -> str:
    domain = domain_of(desired)
    lines = ["- Apps:", "    - Site:"]
    for s in all_services(desired):
        if not s.get("tile"):
            continue
        sub = (s.get("subdomain") or {}).get("primary")
        if not sub:
            continue
        lines += [
            f"        - {s['name']}:",
            f"            href: https://{sub}.{domain}",
        ]
        if s["key"] == "peanut":
            lines += [
                "            widget:",
                "                type: peanut",
                f"                url: http://{LOOPBACK}:8092",
                "                key: ups",
            ]
        if s["key"] in ("pi-hole", "pihole"):
            lines += [
                "            widget:",
                "                type: pihole",
                f"                url: http://{LOOPBACK}:8088",
                "                version: 6",
                "                key: \"{{HOMEPAGE_VAR_PIHOLE_TOKEN}}\"",
            ]
        if s["key"] == "glances" and s.get("network") == "site":
            lines += [
                "            widget:",
                "                type: glances",
                "                url: http://glances:61208",
                "                version: 4",
            ]
    return "\n".join(lines) + "\n"
