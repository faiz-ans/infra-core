"""Generate Caddyfile, Authelia, and Homepage config from desired + pack."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from .directory import authelia_password_hash, file_backend_needs_passwords, ldap_base_dn, sso_groups
from .resolve import LOOPBACK
from .topology import (
    ROOT,
    admin_gui,
    all_services,
    env,
    exception_covers_route,
    exception_covers_service,
    hosts,
    ingress_host,
    placed_keys,
    policy,
    site_of,
)


def domain_of(desired: dict[str, Any]) -> str:
    return str(env(desired).get("domain") or "example.lan")


def authelia_label(desired: dict[str, Any]) -> str:
    """Host label of the placed Authelia service. site.yaml subdomain wins."""
    for service in all_services(desired):
        if service.get("key") == "authelia":
            return str((service.get("subdomain") or {}).get("primary") or "authelia")
    return "authelia"


def web_port(service: dict[str, Any]) -> str | None:
    """Host port Caddy should proxy to. Empty means this service has no web UI."""
    port = (service.get("ports") or {}).get("web")
    if port in (None, ""):
        return None
    return str(port)


def admin_gui_host(desired: dict[str, Any]) -> dict[str, Any] | None:
    """The host whose Cockpit Caddy should publish. The ingress host wins when it has one."""
    ingress_name = (ingress_host(desired) or {}).get("name")
    chosen: dict[str, Any] | None = None
    for host in hosts(desired):
        if not admin_gui(host.get("admin-gui"))["enabled"]:
            continue
        if host.get("name") == ingress_name:
            return host
        if chosen is None:
            chosen = host
    return chosen


def gate_all_routes(desired: dict[str, Any]) -> bool:
    """Forward-auth is opt-in, and still requires both engines to be placed."""
    p = policy(desired)
    if not p["forward_auth"] or p["sso"] != "authelia" or p["ingress"] != "caddy":
        return False
    keys = placed_keys(desired)
    return "authelia" in keys and "caddy" in keys


def _service_excepted(desired: dict[str, Any], service: dict[str, Any]) -> bool:
    return any(exception_covers_service(rule, service) for rule in policy(desired)["auth_exceptions"])


def _route_excepted(desired: dict[str, Any], *tokens: str) -> bool:
    return any(exception_covers_route(rule, *tokens) for rule in policy(desired)["auth_exceptions"])


def service_gated(desired: dict[str, Any], service: dict[str, Any]) -> bool:
    """True when this site block must forward-auth before it fulfills the request.

    The SSO portal itself stays open so a person can sign in. The site-wide
    gate runs only when forward-auth is enabled and both engines are placed.
    Every other route is then gated unless an exception names it. Otherwise
    only a service's own forward-auth mode is gated.
    """
    if service.get("key") == "authelia":
        return False
    if gate_all_routes(desired):
        return not _service_excepted(desired, service)
    return (service.get("sso") or "none") == "forward-auth"


def route_gated(desired: dict[str, Any], *tokens: str) -> bool:
    """Cockpit and the router site follow the site-wide forward-auth switch."""
    if not gate_all_routes(desired):
        return False
    return not _route_excepted(desired, *tokens)


def _sablier_peer(desired: dict[str, Any], service: dict[str, Any]) -> dict[str, Any] | None:
    """The Sablier that shares this container's host and workload user.

    It talks to that user's systemd, which only sees that user's Quadlets.
    Authelia stays running because forward-auth calls it before any plugin.
    """
    if "sablier" not in policy(desired)["plugins"]:
        return None
    if service.get("key") in ("sablier", "authelia", "caddy"):
        return None
    for peer in all_services(desired):
        if peer.get("key") != "sablier":
            continue
        if peer.get("host") == service.get("host") and peer.get("user") == service.get("user"):
            return peer
    return None


def _sablier_names(service: dict[str, Any]) -> list[str]:
    """Systemd user units for this service. Quadlet names each unit after the file."""
    component = str(service.get("component") or service.get("key") or "")
    directory = ROOT / "components" / component
    found: list[str] = []
    if directory.is_dir():
        for pattern in ("*.container", "*.kube"):
            for unit in sorted(directory.glob(pattern)):
                found.append(f"{unit.stem}.service")
    if found:
        return found
    name = str(service.get("name") or service.get("key") or "")
    return [f"{name}.service"] if name else []


# IT Tools is a client-side PWA. After one visit its service worker serves the
# app from cache, so later navigations never reach Caddy. This worker replaces
# that one: it keeps no cache and does not answer fetches, so the browser goes
# back through the gates. The check for /sw.js itself is not authenticated;
# a login redirect would leave the caching worker installed.
IT_TOOLS_SW = (
    "self.addEventListener('install',e=>self.skipWaiting());"
    "self.addEventListener('activate',e=>e.waitUntil((async()=>{"
    "const ks=await caches.keys();"
    "await Promise.all(ks.map(k=>caches.delete(k)));"
    "await self.clients.claim();"
    "const cs=await self.clients.matchAll({type:'window'});"
    "await Promise.all(cs.map(c=>c.navigate(c.url)));"
    "})()));"
)


def sablier_import(desired: dict[str, Any], service: dict[str, Any], ingress_name: str | None) -> str | None:
    """Ask Sablier to wake this container after authentication and before the upstream."""
    peer = _sablier_peer(desired, service)
    names = _sablier_names(service)
    if not peer or not names:
        return None
    port = web_port(peer) or "10000"
    if peer.get("host") and ingress_name and peer.get("host") == ingress_name:
        address = f"127.0.0.1:{port}"
    else:
        address = f"{peer.get('host_ip') or '127.0.0.1'}:{port}"
    query = urlencode([("names", name) for name in names])
    return f'import sablier_gate {address} "/api/strategies/blocking?{query}"'


def upstream_for(service: dict[str, Any], ingress_name: str | None) -> str:
    """Loopback on the ingress host. Another host's address everywhere else."""
    host = service.get("host")
    ip = service.get("host_ip")
    if host and ingress_name and host != ingress_name and ip:
        return str(ip)
    return "127.0.0.1"


def generate_caddyfile(desired: dict[str, Any]) -> str:
    if not policy(desired)["generate_upstream"]:
        return ""
    domain = domain_of(desired)
    ingress_name = (ingress_host(desired) or {}).get("name")
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
        f"		uri /api/authz/forward-auth?authelia_url=https://{authelia_label(desired)}.{domain}/",
        "		copy_headers Remote-User Remote-Groups Remote-Name Remote-Email",
        "	}",
        "}",
        "(authelia_gate_cockpit) {",
        "	forward_auth 127.0.0.1:9091 {",
        f"		uri /api/authz/forward-auth?authelia_url=https://{authelia_label(desired)}.{domain}/",
        "		copy_headers Remote-User Remote-Groups Remote-Name Remote-Email",
        "		header_up -Authorization",
        "	}",
        "}",
        "",
    ]
    if any(service.get("key") == "sablier" for service in all_services(desired)) and "sablier" in policy(desired)["plugins"]:
        lines += [
            "(sablier_gate) {",
            "	forward_auth {args[0]} {",
            "		uri {args[1]}",
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
        if s["key"] == "rustdesk":
            seen.add(primary)
            aliases = sub.get("aliases") or []
            for a in aliases:
                lines += [
                    f"https://{a}.{domain} {{",
                    "	tls internal",
                    f"	redir https://{primary}.{domain}{{uri}} permanent",
                    "}",
                    "",
                ]
            lines += [f"https://{primary}.{domain} {{", "	tls internal"]
            if service_gated(desired, s):
                lines.append("	import authelia_gate")
            lines += [
                "	header Content-Type text/plain",
                "	respond \"RustDesk uses the native client. Point the ID server at this host and the relay at port 21117.\" 200",
                "}",
                "",
            ]
            continue
        up_port = web_port(s)
        if s["key"] == "caddy" or not up_port:
            continue
        seen.add(primary)
        aliases = sub.get("aliases") or []
        for a in aliases:
            lines += [
                f"https://{a}.{domain} {{",
                "	tls internal",
                f"	redir https://{primary}.{domain}{{uri}} permanent",
                "}",
                "",
            ]
        sso = s.get("sso") or "none"
        upstream = upstream_for(s, ingress_name)
        lines += [f"https://{primary}.{domain} {{", "	tls internal"]
        wake = sablier_import(desired, s, ingress_name)
        admin_only = sso == "admin-only" and not gate_all_routes(desired)
        proxy = [
            f"	reverse_proxy {upstream}:{up_port} {{",
            f"		header_up Host {primary}.{domain}",
            f"		header_up X-Forwarded-Host {primary}.{domain}",
            "		header_up X-Forwarded-Proto https",
        ]
        if s["key"] == "radicale":
            proxy += [
                "		header_up -X-Remote-User",
                "		header_up X-Remote-User {http.request.header.Remote-User}",
            ]
        if s["key"] == "collabora":
            proxy += [
                "		flush_interval -1",
                "		transport http {",
                "			read_timeout 3600s",
                "			write_timeout 3600s",
                "		}",
            ]
        if wake:
            # Sablier is ready when systemd is active. The process can still
            # reset the published port until it listens.
            proxy += [
                "		lb_try_duration 30s",
                "		lb_try_interval 250ms",
            ]
        proxy.append("	}")
        if s["key"] == "it-tools":
            lines += [
                "	route {",
                "		handle /sw.js {",
                "			header Cache-Control no-store",
                "			header Content-Type application/javascript",
                f'			respond "{IT_TOOLS_SW}" 200',
                "		}",
            ]
            if service_gated(desired, s):
                lines.append("		import authelia_gate")
            if wake:
                lines.append("\t\t" + wake)
            lines += ["\t" + line for line in proxy]
            lines += ["	}", "}", ""]
            continue
        if admin_only and wake:
            # route keeps source order: authenticate, then Sablier, then the upstream.
            lines += [
                "	route {",
                "		handle /admin* {",
                "			import authelia_gate",
                "\t\t\t" + wake,
                f"			reverse_proxy {upstream}:{up_port}",
                "		}",
                "\t\t" + wake,
            ]
            lines += ["\t" + line for line in proxy]
            lines.append("	}")
        else:
            if service_gated(desired, s):
                lines.append("	import authelia_gate")
            if wake:
                lines.append("\t" + wake)
            portal = policy(desired)["portal_assets"] if s["key"] == "authelia" else ""
            if s["key"] == "authelia":
                lines += [
                    "	handle /pki/local-root.crt {",
                    "		rewrite * /root.crt",
                    "		root * /data/caddy/pki/authorities/local",
                    "		file_server",
                    "	}",
                ]
                if portal:
                    lines += [
                        "	handle_path /portal/* {",
                        f"		root * {portal}",
                        "		file_server",
                        "	}",
                    ]
                    home = next((item for item in all_services(desired) if item.get("key") == "homepage" and web_port(item)), None)
                    if home:
                        home_label = str((home.get("subdomain") or {}).get("primary") or "homepage")
                        home_up = f"{upstream_for(home, ingress_name)}:{web_port(home)}"
                        lines += [
                            "	handle /images/* {",
                            f"		reverse_proxy {home_up} {{",
                            f"			header_up Host {home_label}.{domain}",
                            "		}",
                            "	}",
                        ]
                    # Homepage resolves icon filenames to this CDN in the browser.
                    # The login host must serve them itself; Authelia's policy blocks other origins.
                    lines += [
                        "	handle_path /cdn/* {",
                        "		reverse_proxy https://cdn.jsdelivr.net {",
                        "			header_up Host cdn.jsdelivr.net",
                        "		}",
                        "	}",
                    ]
            if admin_only:
                lines += [
                    "	handle /admin* {",
                    "		import authelia_gate",
                    f"		reverse_proxy {upstream}:{up_port}",
                    "	}",
                ]
            if portal:
                # replace is provided by the optional localhost/caddy-portal image.
                # It runs before the proxy so it sees the HTML body.
                lines += [
                    "	route {",
                    '		replace "</head>" "</head><link rel=\\"stylesheet\\" href=\\"/portal/login.css\\"><script src=\\"/portal/login.js\\" defer></script>"',
                ]
                opened = False
                for line in proxy:
                    if not opened and line.startswith("\treverse_proxy "):
                        lines.append("\t" + line)
                        lines.append("\t\t\theader_up -Accept-Encoding")
                        opened = True
                        continue
                    lines.append("\t" + line)
                lines.append("	}")
            else:
                lines += proxy
        lines += ["}", ""]
    gui = admin_gui_host(desired)
    if gui:
        gui_cfg = admin_gui(gui.get("admin-gui"))
        primary = gui_cfg["primary"]
        gui_upstream = "127.0.0.1"
        if gui.get("name") != ingress_name and gui.get("ip"):
            gui_upstream = str(gui.get("ip"))
        for alias in gui_cfg["aliases"]:
            if not alias or alias == primary or alias in seen:
                continue
            seen.add(alias)
            lines += [
                f"https://{alias}.{domain} {{",
                "	tls internal",
                f"	redir https://{primary}.{domain}{{uri}} permanent",
                "}",
                "",
            ]
        if primary not in seen:
            seen.add(primary)
            lines += [f"https://{primary}.{domain} {{", "	tls internal"]
            if route_gated(desired, primary, *gui_cfg["aliases"]):
                lines.append("	import authelia_gate_cockpit")
            lines += [
                f"	reverse_proxy https://{gui_upstream}:9090 {{",
                f"		header_up Host {primary}.{domain}",
                f"		header_up X-Forwarded-Host {primary}.{domain}",
                "		header_up X-Forwarded-Proto https",
                "		transport http {",
                "			tls_insecure_skip_verify",
                "		}",
                "	}",
                "}",
                "",
            ]
    router = str(env(desired).get("lan_ip") or "").strip()
    if router:
        lines += [f"https://wifi.{domain} {{", "	tls internal"]
        if route_gated(desired, "wifi"):
            lines.append("	import authelia_gate")
        lines += [
            f"	reverse_proxy https://{router} {{",
            "		transport http {",
            "			tls_insecure_skip_verify",
            "		}",
            f"		header_up Host {router}",
            "	}",
            "}",
            "",
        ]
    return "\n".join(lines)


def _authelia_env(name: str) -> str:
    return "'{{ env \"" + name + "\" }}'"


def inject_authelia_ldap_password(text: str) -> str:
    """Give the Authelia container the OpenLDAP admin password it templates."""
    if "LDAP_ADMIN_PASSWORD" in text:
        return text
    line = "Secret=${secrets.openldap.admin_password},type=env,target=LDAP_ADMIN_PASSWORD\n"
    marker = "\n[Service]\n"
    if marker not in text:
        raise ValueError("authelia container unit has no [Service] section for the LDAP password")
    return text.replace(marker, "\n" + line + marker, 1)


def generate_authelia(desired: dict[str, Any]) -> str:
    """OIDC clients are public. SET only creates oidc.pem, not client_secret_digest."""
    if not policy(desired)["generate_upstream"]:
        return ""
    domain = domain_of(desired)
    if policy(desired)["ldap"] == "openldap":
        base = ldap_base_dn(domain)
        auth = [
            "authentication_backend:",
            "  password_reset:",
            "    disable: true",
            "  ldap:",
            "    implementation: custom",
            "    address: ldap://openldap:389",
            "    timeout: 5s",
            "    start_tls: false",
            f"    base_dn: {base}",
            f"    user: cn=admin,{base}",
            f"    password: {_authelia_env('LDAP_ADMIN_PASSWORD')}",
            '    users_filter: "(&({username_attribute}={input})(objectClass=inetOrgPerson))"',
            '    groups_filter: "(&(member={dn})(objectClass=groupOfNames))"',
            "    attributes:",
            "      username: uid",
            "      display_name: cn",
            "      mail: mail",
            "      group_name: cn",
        ]
    else:
        auth = [
            "authentication_backend:",
            "  password_reset:",
            "    disable: true",
            "  file:",
            "    path: /config/userdb/users.yml",
            "    watch: true",
        ]
    clients: list[str] = []
    for service in all_services(desired):
        if service.get("sso") != "oidc":
            continue
        if service["key"] == "opencloud":
            sub = (service.get("subdomain") or {}).get("primary") or "cloud"
            clients += _opencloud_clients(f"{sub}.{domain}")
            continue
        sub = (service.get("subdomain") or {}).get("primary") or service["name"]
        clients += _oidc_client(service, f"{sub}.{domain}")
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
            f"    - domain: '{authelia_label(desired)}.{domain}'",
            "      policy: bypass",
            f"    - domain: '*.{domain}'",
            "      policy: one_factor",
            "session:",
            f"  secret: {_authelia_env('SESSION_SECRET')}",
            "  cookies:",
            "    - name: authelia_session",
            f"      domain: '{domain}'",
            f"      authelia_url: 'https://{authelia_label(desired)}.{domain}'",
            f"      default_redirection_url: 'https://dash.{domain}'",
            "storage:",
            f"  encryption_key: {_authelia_env('STORAGE_ENCRYPTION_KEY')}",
            "  local:",
            "    path: /data/db.sqlite3",
            "notifier:",
            "  filesystem:",
            "    filename: /data/notification.txt",
            "identity_providers:",
            "  oidc:",
            f"    hmac_secret: {_authelia_env('OIDC_HMAC_SECRET')}",
            "    jwks:",
            '      - key: {{ secret "/config/userdb/oidc.pem" | mindent 10 "|" | msquote }}',
            "    cors:",
            "      endpoints: [authorization, token, revocation, introspection, userinfo]",
            "      allowed_origins_from_client_redirect_uris: true",
            "    authorization_policies:",
            "      users:",
            "        default_policy: deny",
            "        rules:",
            "          - policy: one_factor",
            "            subject: 'group:users'",
            "    claims_policies:",
            "      opencloud:",
            "        id_token: [email, email_verified, preferred_username, name, groups]",
            "    clients:",
            *clients,
            "",
        ]
    )


def _oidc_client(service: dict[str, Any], host: str) -> list[str]:
    """Redirects and token auth match what each app actually sends."""
    key = service["key"]
    secret = _authelia_env("OIDC_CLIENT_SECRET")
    if key == "jotty":
        redirects = [f"https://{host}/api/oidc/callback"]
        confidential = True
        pkce = True
    elif key == "bytestash":
        redirects = [f"https://{host}/api/auth/oidc/callback"]
        confidential = True
        pkce = True
    elif key == "linkding":
        redirects = [f"https://{host}/oidc/callback/"]
        confidential = True
        pkce = False
    else:
        redirects = [f"https://{host}/", f"https://{host}/oidc-callback.html"]
        confidential = False
        pkce = False
    lines = [
        f"      - client_id: {key}",
        f"        client_name: {service['name']}",
        f"        public: {'false' if confidential else 'true'}",
        "        authorization_policy: one_factor",
        "        scopes: [openid, groups, profile, email]",
        "        redirect_uris: [" + ", ".join(f"'{uri}'" for uri in redirects) + "]",
    ]
    if confidential:
        lines += [
            f"        client_secret: {secret}",
            "        token_endpoint_auth_method: client_secret_post",
        ]
    else:
        lines.append("        token_endpoint_auth_method: none")
    if pkce:
        lines += [
            "        require_pkce: true",
            "        pkce_challenge_method: S256",
        ]
    return lines


def _opencloud_clients(host: str) -> list[str]:
    """Public clients. The web app hangs without silent-redirect, implicit consent, and CORS."""
    web = [
        "      - client_id: opencloud",
        "        client_name: OpenCloud",
        "        public: true",
        "        authorization_policy: users",
        "        consent_mode: implicit",
        "        claims_policy: opencloud",
        "        require_pkce: true",
        "        pkce_challenge_method: S256",
        "        scopes: [openid, groups, profile, email]",
        "        redirect_uris:",
        f"          - 'https://{host}/'",
        f"          - 'https://{host}/oidc-callback.html'",
        f"          - 'https://{host}/oidc-silent-redirect.html'",
        "        response_types: [code]",
        "        grant_types: [authorization_code]",
        "        access_token_signed_response_alg: RS256",
        "        userinfo_signed_response_alg: none",
        "        token_endpoint_auth_method: none",
        "        requested_audience_mode: implicit",
        "        audience: [opencloud]",
    ]
    apps = [
        ("opencloud-android", "OpenCloud Android", ["oc://android.opencloud.eu"]),
        ("opencloud-ios", "OpenCloud iOS", ["oc://ios.opencloud.eu", "oc.ios://ios.opencloud.eu"]),
        ("opencloud-desktop", "OpenCloud Desktop", ["http://127.0.0.1", "http://localhost"]),
    ]
    lines = list(web)
    for client_id, name, redirects in apps:
        lines += [
            f"      - client_id: {client_id}",
            f"        client_name: {name}",
            "        public: true",
            "        authorization_policy: users",
            "        consent_mode: pre-configured",
            "        pre_configured_consent_duration: 1y",
            "        require_pkce: true",
            "        pkce_challenge_method: S256",
            "        scopes: [openid, offline_access, groups, profile, email]",
            "        redirect_uris:",
            *[f"          - '{uri}'" for uri in redirects],
            "        response_types: [code]",
            "        grant_types: [authorization_code, refresh_token]",
            "        access_token_signed_response_alg: RS256",
            "        userinfo_signed_response_alg: none",
            "        token_endpoint_auth_method: none",
            "        requested_audience_mode: implicit",
            f"        audience: [{client_id}]",
        ]
    return lines


def generate_authelia_users(desired: dict[str, Any], passwords: dict[str, str] | None = None) -> str:
    """File-backend users.yml. Disjoint SSO uses secrets.site.users.<name>.password."""
    if not policy(desired)["generate_upstream"]:
        return ""
    passwords = passwords or {}
    require = file_backend_needs_passwords(desired)
    lines = ["users:"]
    missing = []
    for u in site_of(desired).get("users") or []:
        name = str(u.get("name") or "")
        groups = sso_groups(u)
        password = passwords.get(name) or ""
        if require and not password:
            missing.append(name)
            hashed = "*"
        elif password:
            hashed = authelia_password_hash(password)
        else:
            hashed = "*"
        lines += [
            f"  {name}:",
            f"    displayname: {u.get('displayname') or name}",
            f"    email: {u.get('email') or name + '@' + domain_of(desired)}",
            f"    password: '{hashed}'",
            f"    groups: {groups}",
        ]
    if missing:
        from .secrets import SecretError

        listed = ", ".join(missing)
        raise SecretError(
            "site users need secrets.site.users.<name>.password "
            f"(missing: {listed})"
        )
    return "\n".join(lines)
