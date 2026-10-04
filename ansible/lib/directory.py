"""Site directory accounts: OpenLDAP LDIF, SSSD, and SMB password material.

LDAP is the source of truth only when identity.ldap is openldap and that
service is placed. POSIX groups (ou=groups) back SSSD and SMB. groupOfNames
(ou=roles) backs Authelia. The two object classes cannot share one entry.
"""
from __future__ import annotations

import base64
import hashlib
import os
import subprocess
from typing import Any

from .secrets import SecretError, split_secrets
from .topology import all_services, policy, roots, site_of

LDAP_PORT = 1389
UID_BASE = 20001
GID_BASE = 20000
LOGIN_SHELL = "/usr/sbin/nologin"


def people_homes(filesystem: str, web: str) -> bool:
    """A home is created when either access path is in use. Existing homes stay."""
    return filesystem != "none" or web != "none"


def ldap_base_dn(domain: str) -> str:
    """osixia turns LDAP_DOMAIN home.lan into dc=home,dc=lan."""
    labels = [part for part in domain.strip().split(".") if part]
    return ",".join(f"dc={part}" for part in labels)


def ldap_service(desired: dict[str, Any]) -> dict[str, Any] | None:
    for service in all_services(desired):
        if service.get("key") == "openldap":
            return service
    return None


def ldap_is_sot(desired: dict[str, Any]) -> bool:
    return policy(desired)["ldap"] == "openldap" and ldap_service(desired) is not None


def sso_groups(user: dict[str, Any]) -> list[str]:
    """Authelia groups. appadmin is admins; every site user is users."""
    groups = ["users"]
    if "appadmin" in (user.get("roles") or []):
        groups.append("admins")
    for name in user.get("groups") or []:
        text = str(name)
        if text and text not in groups:
            groups.append(text)
    return groups


def smb_groups(user: dict[str, Any]) -> list[str]:
    """SMB groups. Every site user is in all, plus any group they list."""
    groups = ["all"]
    for name in user.get("groups") or []:
        text = str(name)
        if text and text not in groups:
            groups.append(text)
    return groups


def _ordered_groups(names: set[str]) -> list[str]:
    head = [name for name in ("all", "users", "admins") if name in names]
    rest = sorted(name for name in names if name not in head)
    return head + rest


def _dn_escape(value: str) -> str:
    out: list[str] = []
    for index, char in enumerate(value):
        if char in ',+"\\<>;=' or ord(char) < 32 or (char == " " and index in (0, len(value) - 1)):
            out.append("\\" + char)
        else:
            out.append(char)
    return "".join(out)


def _attr(name: str, value: str) -> str:
    text = str(value)
    if text.startswith((" ", ":", "<")) or text.endswith(" ") or any(ord(char) < 32 for char in text):
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return f"{name}:: {encoded}"
    return f"{name}: {text}"


def _ssha(password: str) -> str:
    salt = os.urandom(8)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


def authelia_password_hash(password: str) -> str:
    """SHA512-crypt hash Authelia's file backend accepts."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./"
    salt = "".join(alphabet[byte % len(alphabet)] for byte in os.urandom(16))
    proc = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin", "-salt", salt],
        input=password.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    hashed = proc.stdout.decode("utf-8").strip()
    if proc.returncode != 0 or not hashed.startswith("$6$"):
        raise SecretError("could not hash a site user password for Authelia")
    return hashed


def file_backend_needs_passwords(desired: dict[str, Any]) -> bool:
    """Disjoint SSO stores the site password in Authelia users.yml."""
    chosen = policy(desired)
    return (
        chosen["ldap"] != "openldap"
        and chosen["sso"] == "authelia"
        and bool(chosen["generate_upstream"])
    )


def _user_password(secrets: dict[str, Any], name: str) -> str:
    site, _hosts = split_secrets(secrets)
    body = (site.get("users") or {}).get(name)
    if not isinstance(body, dict):
        return ""
    value = body.get("password")
    if value is None:
        return ""
    return str(value)


def require_user_passwords(secrets: dict[str, Any], users: list[dict[str, Any]]) -> dict[str, str]:
    missing = []
    found: dict[str, str] = {}
    for user in users:
        name = str(user.get("name") or "")
        if not name:
            continue
        password = _user_password(secrets, name)
        if not password:
            missing.append(name)
        else:
            found[name] = password
    if missing:
        listed = ", ".join(missing)
        raise SecretError(
            "site users need secrets.site.users.<name>.password "
            f"(missing: {listed})"
        )
    return found


def require_admin_password(secrets: dict[str, Any]) -> str:
    site, _hosts = split_secrets(secrets)
    password = str(((site.get("openldap") or {}).get("admin_password")) or "")
    if not password:
        raise SecretError("LDAP needs secrets.site.openldap.admin_password")
    if "\n" in password or "#" in password:
        raise SecretError("secrets.site.openldap.admin_password cannot contain a newline or '#'")
    return password


def ldap_uri(host_name: str, service: dict[str, Any]) -> str:
    if service.get("host") == host_name:
        return f"ldap://127.0.0.1:{LDAP_PORT}"
    return f"ldap://{service.get('host_ip') or '127.0.0.1'}:{LDAP_PORT}"


def render_sssd(desired: dict[str, Any], host_name: str, admin_password: str) -> str:
    service = ldap_service(desired)
    if service is None:
        raise SecretError("identity.ldap is openldap but openldap is not placed")
    domain = str((site_of(desired).get("env") or {}).get("domain") or "")
    base = ldap_base_dn(domain)
    if "\n" in admin_password or "#" in admin_password:
        raise SecretError("secrets.site.openldap.admin_password cannot contain a newline or '#'")
    uri = ldap_uri(host_name, service)
    return "\n".join(
        [
            "[sssd]",
            "services = nss, pam",
            "domains = site",
            "config_file_version = 2",
            "",
            "[nss]",
            "enum_cache_timeout = 60",
            "",
            "[domain/site]",
            "id_provider = ldap",
            "auth_provider = ldap",
            f"ldap_uri = {uri}",
            "ldap_schema = rfc2307",
            "ldap_id_mapping = false",
            "enumerate = true",
            "ldap_referrals = false",
            f"ldap_search_base = {base}",
            f"ldap_user_search_base = ou=users,{base}",
            f"ldap_group_search_base = ou=groups,{base}",
            "ldap_user_object_class = posixAccount",
            "ldap_group_object_class = posixGroup",
            "ldap_user_name = uid",
            "ldap_group_name = cn",
            "ldap_group_member = memberUid",
            "ldap_user_home_directory = homeDirectory",
            "ldap_user_shell = loginShell",
            f"ldap_default_bind_dn = cn=admin,{base}",
            "ldap_default_authtok_type = password",
            f"ldap_default_authtok = {admin_password}",
            "ldap_id_use_start_tls = false",
            "ldap_tls_reqcert = never",
            "cache_credentials = true",
            "ldap_network_timeout = 5",
            "",
        ]
    )


def _accounts(desired: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    site = site_of(desired)
    domain = str((site.get("env") or {}).get("domain") or "")
    base = ldap_base_dn(domain)
    user_root = roots(desired)["users"]
    users = [user for user in (site.get("users") or []) if user.get("name")]
    return base, user_root, users


def build_ldif(desired: dict[str, Any], passwords: dict[str, str]) -> tuple[str, str]:
    """Return (add LDIF, modify LDIF). Passwords are SSHA and only in the modify file."""
    base, user_root, users = _accounts(desired)
    users_sorted = sorted(users, key=lambda user: str(user["name"]))
    uids = {str(user["name"]): UID_BASE + index for index, user in enumerate(users_sorted)}
    posix_names: set[str] = set()
    role_names: set[str] = set()
    posix_members: dict[str, list[str]] = {}
    role_members: dict[str, list[str]] = {}
    for user in users_sorted:
        name = str(user["name"])
        for group in smb_groups(user):
            posix_names.add(group)
            posix_members.setdefault(group, []).append(name)
        for group in sso_groups(user):
            role_names.add(group)
            posix_names.add(group)
            role_members.setdefault(group, []).append(name)
            posix_members.setdefault(group, [])
            if name not in posix_members[group]:
                posix_members[group].append(name)
    gids = {name: GID_BASE + index for index, name in enumerate(_ordered_groups(posix_names))}
    primary = gids.get("all", GID_BASE)

    add: list[str] = []
    modify: list[str] = []

    def entry(lines: list[str], dn: str, body: list[str], change: str) -> None:
        lines.append(f"dn: {dn}")
        lines.append(f"changetype: {change}")
        lines.extend(body)
        lines.append("")

    for ou in ("users", "groups", "roles"):
        entry(
            add,
            f"ou={ou},{base}",
            ["objectClass: organizationalUnit", f"ou: {ou}"],
            "add",
        )

    for user in users_sorted:
        name = str(user["name"])
        display = str(user.get("displayname") or name)
        mail = str(user.get("email") or f"{name}@{(site_of(desired).get('env') or {}).get('domain') or 'local'}")
        uid_dn = f"uid={_dn_escape(name)},ou=users,{base}"
        attrs = [
            "objectClass: inetOrgPerson",
            "objectClass: posixAccount",
            _attr("uid", name),
            _attr("cn", display),
            _attr("sn", display),
            _attr("mail", mail),
            _attr("uidNumber", str(uids[name])),
            _attr("gidNumber", str(primary)),
            _attr("homeDirectory", f"{user_root.rstrip('/')}/{name}"),
            _attr("loginShell", LOGIN_SHELL),
        ]
        entry(add, uid_dn, attrs, "add")
        entry(
            modify,
            uid_dn,
            [
                "replace: cn",
                _attr("cn", display),
                "-",
                "replace: sn",
                _attr("sn", display),
                "-",
                "replace: mail",
                _attr("mail", mail),
                "-",
                "replace: uidNumber",
                _attr("uidNumber", str(uids[name])),
                "-",
                "replace: gidNumber",
                _attr("gidNumber", str(primary)),
                "-",
                "replace: homeDirectory",
                _attr("homeDirectory", f"{user_root.rstrip('/')}/{name}"),
                "-",
                "replace: loginShell",
                _attr("loginShell", LOGIN_SHELL),
                "-",
                "replace: userPassword",
                _attr("userPassword", _ssha(passwords[name])),
            ],
            "modify",
        )

    for name in _ordered_groups(posix_names):
        members = sorted(posix_members.get(name) or [])
        if not members:
            continue
        dn = f"cn={_dn_escape(name)},ou=groups,{base}"
        body = ["objectClass: posixGroup", _attr("cn", name), _attr("gidNumber", str(gids[name]))]
        body.extend(_attr("memberUid", member) for member in members)
        entry(add, dn, body, "add")
        replace = ["replace: gidNumber", _attr("gidNumber", str(gids[name])), "-", "replace: memberUid"]
        replace.extend(_attr("memberUid", member) for member in members)
        entry(modify, dn, replace, "modify")

    for name in _ordered_groups(role_names):
        members = sorted(role_members.get(name) or [])
        if not members:
            continue
        dn = f"cn={_dn_escape(name)},ou=roles,{base}"
        body = ["objectClass: groupOfNames", _attr("cn", name)]
        body.extend(
            _attr("member", f"uid={_dn_escape(member)},ou=users,{base}") for member in members
        )
        entry(add, dn, body, "add")
        replace = ["replace: member"]
        replace.extend(
            _attr("member", f"uid={_dn_escape(member)},ou=users,{base}") for member in members
        )
        entry(modify, dn, replace, "modify")

    return "\n".join(add) + "\n", "\n".join(modify) + "\n"
