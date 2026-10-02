"""Generate Caddyfile, Authelia, and Homepage config from desired + pack."""
from __future__ import annotations

from typing import Any

from .resolve import LOOPBACK
from .topology import all_services, env, hosts, ingress_host, policy, site_of


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
        if not host.get("admin-gui"):
            continue
        if host.get("name") == ingress_name:
            return host
        if chosen is None:
            chosen = host
    return chosen


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
        "",
    ]
    seen = set()
    for s in all_services(desired):
        sub = s.get("subdomain") or {}
        primary = sub.get("primary")
        if not primary or primary in seen:
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
    gui = admin_gui_host(desired)
    if gui:
        gui_upstream = "127.0.0.1"
        if gui.get("name") != ingress_name and gui.get("ip"):
            gui_upstream = str(gui.get("ip"))
        lines += [
            f"https://cockpit.{domain} {{",
            "	tls internal",
            f"	reverse_proxy https://{gui_upstream}:9090 {{",
            f"		header_up Host cockpit.{domain}",
            f"		header_up X-Forwarded-Host cockpit.{domain}",
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
        lines += [
            f"https://wifi.{domain} {{",
            "	tls internal",
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


def ldap_base_dn(domain: str) -> str:
    """osixia turns LDAP_DOMAIN home.lan into dc=home,dc=lan."""
    labels = [part for part in domain.strip().split(".") if part]
    return ",".join(f"dc={part}" for part in labels)


def _authelia_env(name: str) -> str:
    return "'{{ env \"" + name + "\" }}'"


def inject_authelia_ldap_password(pod_text: str) -> str:
    """Give the Authelia container the OpenLDAP admin password it templates."""
    if "LDAP_ADMIN_PASSWORD" in pod_text:
        return pod_text
    block = (
        "    - name: LDAP_ADMIN_PASSWORD\n"
        "      valueFrom:\n"
        "        secretKeyRef:\n"
        "          name: ${secrets.openldap.admin_password}\n"
        "          key: value\n"
    )
    needle = "    ports:\n"
    if needle not in pod_text:
        raise ValueError("authelia pod.yaml has no ports block for the LDAP password")
    return pod_text.replace(needle, block + needle, 1)


def generate_authelia(desired: dict[str, Any]) -> str:
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
    if not policy(desired)["generate_upstream"]:
        return ""
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
