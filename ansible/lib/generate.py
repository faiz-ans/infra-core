"""Generate Caddyfile, Authelia, and Homepage config from desired + pack."""
from __future__ import annotations

from typing import Any

from .directory import authelia_password_hash, file_backend_needs_passwords, ldap_base_dn, sso_groups
from .resolve import LOOPBACK
from .topology import admin_gui, all_services, env, hosts, ingress_host, placed_keys, policy, site_of


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
    """Authelia and Caddy together authenticate every request before the upstream."""
    p = policy(desired)
    if p["sso"] != "authelia" or p["ingress"] != "caddy":
        return False
    keys = placed_keys(desired)
    return "authelia" in keys and "caddy" in keys


def _exempt(desired: dict[str, Any], *tokens: str) -> bool:
    exceptions = set(policy(desired)["auth_exceptions"])
    return any(token and token in exceptions for token in tokens)


def service_gated(desired: dict[str, Any], service: dict[str, Any]) -> bool:
    """True when this site block must forward-auth before it fulfills the request.

    The SSO portal itself stays open so a person can sign in. With both engines
    placed, every other route is gated unless the operator listed an exception.
    Without both engines, only a service's own forward-auth mode is gated.
    """
    if service.get("key") == "authelia":
        return False
    sub = service.get("subdomain") or {}
    if gate_all_routes(desired):
        return not _exempt(desired, str(service.get("key") or ""), str(service.get("name") or ""), str(sub.get("primary") or ""))
    return (service.get("sso") or "none") == "forward-auth"


def route_gated(desired: dict[str, Any], *tokens: str) -> bool:
    """Cockpit and the router site follow the same default as services."""
    if not gate_all_routes(desired):
        return False
    return not _exempt(desired, *tokens)


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
        if service_gated(desired, s):
            lines.append("	import authelia_gate")
        if s["key"] == "authelia":
            lines += [
                "	handle /pki/local-root.crt {",
                "		rewrite * /root.crt",
                "		root * /data/caddy/pki/authorities/local",
                "		file_server",
                "	}",
            ]
        if sso == "admin-only" and not gate_all_routes(desired):
            lines += [
                "	handle /admin* {",
                "		import authelia_gate",
                f"		reverse_proxy {upstream}:{up_port}",
                "	}",
            ]
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
        proxy.append("	}")
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
