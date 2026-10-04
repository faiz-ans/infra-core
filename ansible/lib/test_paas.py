"""Unit tests for topology, resolver, generators, plan, and Quadlet strip."""
from __future__ import annotations

import unittest
from pathlib import Path

from .directory import (
    authelia_password_hash,
    build_ldif,
    file_backend_needs_passwords,
    people_homes,
    render_sssd,
    require_user_passwords,
    sso_groups,
)
from .diff import fingerprints, service_delta, set_delta, user_delta
from .observed import merge_observed, scaffold_desired, scaffold_disks
from .generate import (
    generate_authelia,
    generate_authelia_users,
    generate_caddyfile,
    inject_authelia_ldap_password,
    ldap_base_dn,
)
from .inventory import inventory_dict
from .plan import build_plan, disk_mounts, import_blocks, import_nfs, inferred_nfs, root_binds
from .quadlet import read_utf8, strip_yaml_text
from .resolve import LOOPBACK, bind, render
from .secrets import SecretError, mark_root_hosts, podman_catalog, resolve_secret, split_secrets
from .topology import (
    admin_gui,
    all_services,
    key_only_ready,
    load_desired,
    load_pack,
    validate_placement,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "site.example.yaml"


class TestExample(unittest.TestCase):
    def setUp(self) -> None:
        self.desired = load_desired(EXAMPLE)

    def test_placement_ok(self) -> None:
        self.assertEqual(validate_placement(self.desired), [])

    def test_glances_only_where_listed(self) -> None:
        keys = {(s["host"], s["key"]) for s in all_services(self.desired)}
        self.assertNotIn(("storage", "glances"), keys)
        self.assertIn(("compute", "glances"), keys)

    def test_openldap_must_be_placed(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["identity"]["ldap"] = "openldap"
        errs = validate_placement(bad)
        self.assertTrue(any("openldap" in e for e in errs))

    def test_two_caddy_is_error(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["hosts"][1]["operations"]["workload"]["services"]["caddy"] = None
        errs = validate_placement(bad)
        self.assertTrue(any("caddy" in e for e in errs))

    def test_key_only_ready(self) -> None:
        self.assertEqual(key_only_ready(self.desired), [])
        bad = load_desired(EXAMPLE)
        bad["site"]["hosts"][0]["users"][0]["ssh-keys"] = []
        self.assertTrue(key_only_ready(bad))

    def test_resolver_namespaces(self) -> None:
        m = bind(self.desired, self.desired["site"]["hosts"][0])
        self.assertNotIn("DOMAIN", m)
        self.assertNotIn("NAS_LAN_IP", m)
        self.assertEqual(m["site.env.domain"], "example.lan")
        self.assertEqual(m["site.networking.ingress.host.ip"], "10.0.0.10")
        self.assertEqual(m["host-loopback-mapped-ip"], LOOPBACK)
        self.assertIn(":8443", m["site.homepage.allowed_hosts"])
        self.assertEqual(render("https://cloud.${site.env.domain}", m), "https://cloud.example.lan")
        mantle = self.desired["site"]["hosts"][1]
        mantle["env"] = {"windows": "/mnt/host/c"}
        bound = bind(self.desired, mantle)
        self.assertEqual(bound["host.env.windows"], "/mnt/host/c")
        self.assertEqual(render("${host.env.windows}", bound), "/mnt/host/c")
        self.assertEqual(bound["site.hosts.compute.ip"], "10.0.0.11")
        self.assertEqual(bound["site.hosts.compute.env.windows"], "/mnt/host/c")
        core = bind(self.desired, self.desired["site"]["hosts"][0])
        self.assertNotIn("host.env.windows", core)
        self.assertEqual(render("${site.hosts.compute.ip}", core), "10.0.0.11")
        self.assertEqual(core["site.hosts.compute.env.windows"], "/mnt/host/c")
        self.assertEqual(render("${secrets.immich.database_password}", m), "immich_database_password")
        self.assertNotIn("x", render("${secrets.pi-hole.web_password}", m))

    def test_secret_shorthand_site_and_host(self) -> None:
        tree = {
            "secrets": {
                "site": {"authelia": {"session": "site-session"}},
                "hosts": {
                    "core": {"pi-hole": {"web_password": "core-pw"}},
                    "mantle": {"pi-hole": {"web_password": "mantle-pw"}},
                },
            }
        }
        site, hosts = split_secrets(tree)
        authelia = dict(service="authelia", host="core", site=site, hosts=hosts)
        for ref in (
            "secrets.site.authelia.session",
            "secrets.authelia.session",
            "secrets.session",
        ):
            found = resolve_secret(ref, **authelia)
            self.assertEqual(found.podman_name, "authelia_session")
            self.assertEqual(found.value, "site-session")
            self.assertEqual(found.host, "")
        pihole = dict(service="pi-hole", host="core", site=site, hosts=hosts)
        for ref in (
            "secrets.hosts.core.pi-hole.web_password",
            "secrets.host.pi-hole.web_password",
            "secrets.host.web_password",
        ):
            found = resolve_secret(ref, **pihole)
            self.assertEqual(found.podman_name, "pi-hole_web_password")
            self.assertEqual(found.value, "core-pw")
            self.assertEqual(found.host, "core")
        with self.assertRaises(SecretError):
            resolve_secret("secrets.hosts.core.pihole.web_password", **pihole)
        mantle = resolve_secret("secrets.host.web_password", service="pi-hole", host="mantle", site=site, hosts=hosts)
        self.assertEqual(mantle.podman_name, "pi-hole_web_password")
        self.assertEqual(mantle.value, "mantle-pw")
        borrowed = resolve_secret(
            "secrets.host.pi-hole.web_password",
            service="authelia",
            host="core",
            site=site,
            hosts=hosts,
        )
        self.assertEqual(borrowed.value, "core-pw")
        self.assertEqual(borrowed.podman_name, "authelia_pi-hole_web_password")
        home = resolve_secret(
            "secrets.host.pi-hole.web_password",
            service="homepage",
            host="core",
            site=site,
            hosts=hosts,
        )
        self.assertEqual(home.podman_name, "homepage_pi-hole_web_password")
        self.assertEqual(home.value, "core-pw")
        other = resolve_secret(
            "secrets.host.mantle.pi-hole.web_password",
            service="homepage",
            host="core",
            site=site,
            hosts=hosts,
        )
        self.assertEqual(other.podman_name, "homepage_mantle_pi-hole_web_password")
        self.assertEqual(other.value, "mantle-pw")
        self.assertEqual(other.host, "mantle")
        with self.assertRaises(SecretError):
            resolve_secret("secrets.host.session", service="authelia", host="core", site=site, hosts=hosts)
        rendered = render(
            "Secret=${secrets.host.web_password}",
            {},
            service="pi-hole",
            host="mantle",
            secrets=tree,
        )
        self.assertEqual(rendered, "Secret=pi-hole_web_password")
        catalog = podman_catalog(tree)
        core_names = {item["name"]: item["value"] for item in catalog if item["host"] in ("", "core")}
        mantle_names = {item["name"]: item["value"] for item in catalog if item["host"] in ("", "mantle")}
        self.assertEqual(core_names["pi-hole_web_password"], "core-pw")
        self.assertEqual(mantle_names["pi-hole_web_password"], "mantle-pw")
        self.assertEqual(core_names["authelia_session"], "site-session")
        self.assertNotIn("mantle-pw", core_names.values())
        compute = bind(self.desired, self.desired["site"]["hosts"][1])
        self.assertEqual(compute["host.resources.gpu.gpu0.id"], "gpu0")
        self.assertEqual(compute["host.resources.gpu.gpu0.name"], "NVIDIA GeForce RTX 2060")
        self.assertEqual(
            compute["host.resources.gpu.gpu0.uuid"],
            "GPU-00000000-0000-0000-0000-000000000001",
        )
        self.assertEqual(compute["host.resources.gpu.gpu0.resource"], "nvidia.com/gpu")
        self.assertNotIn("host.resources.gpu.gpu0.count", compute)
        self.assertNotIn("host.resources.gpu.gpu0.visible", compute)
        self.assertNotIn("host.resources.gpu.gpu0.resource-count", compute)
        self.assertNotIn("host.resources.gpu.gpu0.device", compute)
        self.assertNotIn("host.resources.gpu.gpu0", compute)
        self.assertEqual(
            render("${host.resources.gpu.gpu0.resource}: 1", compute),
            "nvidia.com/gpu: 1",
        )
        storage = bind(self.desired, self.desired["site"]["hosts"][0])
        self.assertNotIn("host.resources.gpu.gpu0.id", storage)
        self.assertEqual(compute["host.data.roots.appdata"], "/var/lib/site-appdata")
        self.assertEqual(compute["host.appdata"], "/var/lib/site-appdata")
        self.assertEqual(storage["host.appdata"], "/appdata")
        self.assertEqual(
            render("${host.data.roots.appdata}/caddy", compute),
            "/var/lib/site-appdata/caddy",
        )
        self.assertNotIn("host.data.roots.appdata", storage)

    def test_caddy_and_homepage(self) -> None:
        caddy = generate_caddyfile(self.desired)
        self.assertIn("https://authelia.example.lan", caddy)
        self.assertIn("handle /pki/local-root.crt", caddy)
        self.assertIn("root * /data/caddy/pki/authorities/local", caddy)
        self.assertIn("https://opencloud.example.lan", caddy)
        self.assertIn("https://homepage.example.lan", caddy)
        self.assertIn("https://dns.example.lan", caddy)
        self.assertNotIn("https://auth.example.lan", caddy)
        self.assertNotIn("https://cloud.example.lan", caddy)
        self.assertIn("reverse_proxy 127.0.0.1:9091", caddy)
        self.assertIn("reverse_proxy 10.0.0.11:61208", caddy)
        self.assertNotIn("https://users.example.lan", caddy)
        self.assertIn("https://glances.example.lan", caddy)
        self.assertNotIn("https://host.example.lan", caddy)
        self.assertNotIn("reverse_proxy 127.0.0.1:389", caddy)
        self.assertIn("https://cockpit.example.lan {", caddy)
        self.assertIn("redir https://sys.example.lan{uri} permanent", caddy)
        cockpit = caddy.split("https://sys.example.lan {", 1)[1].split("\nhttps://", 1)[0]
        self.assertIn("reverse_proxy https://127.0.0.1:9090", cockpit)
        self.assertIn("header_up Host sys.example.lan", cockpit)
        self.assertIn("tls_insecure_skip_verify", cockpit)
        self.assertNotIn("authelia_gate", cockpit)

    def test_cockpit_follows_admin_gui_host(self) -> None:
        absent = load_desired(EXAMPLE)
        absent["site"]["hosts"][0]["admin-gui"] = False
        self.assertNotIn("sys.example.lan", generate_caddyfile(absent))
        self.assertNotIn("cockpit.example.lan", generate_caddyfile(absent))
        remote = load_desired(EXAMPLE)
        remote["site"]["hosts"][0]["admin-gui"] = False
        remote["site"]["hosts"][1]["admin-gui"] = True
        caddy = generate_caddyfile(remote)
        self.assertIn("https://cockpit.example.lan {", caddy)
        self.assertIn("reverse_proxy https://10.0.0.11:9090", caddy)
        self.assertNotIn("sys.example.lan", caddy)

    def test_admin_gui_normalize(self) -> None:
        self.assertEqual(
            admin_gui(True),
            {"enabled": True, "primary": "cockpit", "aliases": []},
        )
        self.assertEqual(
            admin_gui({"enabled": True, "primary": "sys", "aliases": ["cockpit"]}),
            {"enabled": True, "primary": "sys", "aliases": ["cockpit"]},
        )
        self.assertFalse(admin_gui({"enabled": False, "primary": "sys"})["enabled"])
        self.assertFalse(admin_gui(False)["enabled"])
        plan = build_plan(self.desired)
        self.assertEqual(
            plan["hosts"][0]["admin-gui"],
            {"enabled": True, "primary": "sys", "aliases": ["cockpit"]},
        )

    def test_wireguard_ui_stays_rootless(self) -> None:
        self.assertEqual(load_pack()["services"]["wireguard"]["privilege"], "rootless")
        unit = (ROOT / "components" / "wg-easy" / "wg-easy.container").read_text(encoding="utf-8")
        entry = (ROOT / "components" / "wg-easy" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("Network=host", unit)
        self.assertNotIn("AddCapability", unit)
        self.assertIn("/opt/wg-handoff", unit)
        self.assertIn("/opt/wg-handoff/bin", entry)
        for name in ("wg", "wg-quick", "iptables"):
            link = ROOT / "components" / "wg-easy" / "handoff" / "bin" / name
            self.assertTrue(link.is_symlink(), name)
            self.assertTrue(link.exists(), name)
        desired = {
            "site": {
                "hosts": [
                    {
                        "name": "core",
                        "operations": {"workload": {"services": {"wireguard": None}}},
                    }
                ]
            }
        }
        items = podman_catalog({"site": {"wireguard": {"ui_password": "pw"}}})
        mark_root_hosts(desired, {"site": {"wireguard": {"ui_password": "pw"}}}, ROOT / "components", items)
        secret = next(item for item in items if item["name"] == "wireguard_ui_password")
        self.assertEqual(secret["root_hosts"], [])

    def test_tunnel_port_redirects_stay_on_this_host(self) -> None:
        script = (ROOT / "ansible" / "roles" / "lan_bind" / "files" / "lan-bind").read_text(encoding="utf-8")
        redirects = [
            line.strip()
            for line in script.splitlines()
            if "PREROUTING" in line and "REDIRECT" in line
        ]
        self.assertGreaterEqual(len(redirects), 3)
        for line in redirects:
            self.assertIn("--dst-type LOCAL", line)
        seed = (ROOT / "components" / "wg-easy" / "seed-mtu.mjs").read_text(encoding="utf-8")
        self.assertIn("UPDATE clients_table SET mtu = 1280", seed)
        self.assertIn("UPDATE user_configs_table SET default_mtu = 1280", seed)

    def test_enabling_wireguard_reapplies_lan_bind(self) -> None:
        applied = fingerprints(self.desired)
        current = load_desired(EXAMPLE)
        current["site"]["hosts"][0]["operations"]["workload"]["services"]["wireguard"] = None
        delta = set_delta(current, applied)
        added = {item["key"] for item in delta["services"]["add"]}
        self.assertIn("wireguard", added)
        self.assertTrue(delta["sections"]["lan_bind"])
        self.assertTrue(delta["sections"]["quadlets"])

    def test_caddy_remote_web_and_router(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["env"]["lan_ip"] = "192.0.2.1"
        d["site"]["hosts"][0]["operations"]["workload"]["services"]["wireguard"] = None
        d["site"]["hosts"][1]["operations"]["workload"]["services"]["immich"] = {
            "name": "immich",
            "subdomain": {"primary": "photos", "aliases": ["immich"]},
        }
        caddy = generate_caddyfile(d)
        self.assertIn("https://wireguard.example.lan", caddy)
        self.assertNotIn("https://vpn.example.lan", caddy)
        self.assertIn("reverse_proxy 127.0.0.1:51821", caddy)
        self.assertIn("https://photos.example.lan", caddy)
        self.assertIn("reverse_proxy 10.0.0.11:2283", caddy)
        self.assertIn("https://wifi.example.lan", caddy)
        self.assertIn("tls_insecure_skip_verify", caddy)
        self.assertIn("reverse_proxy https://192.0.2.1", caddy)

    def test_generate_flags_off(self) -> None:
        from .topology import policy

        d = load_desired(EXAMPLE)
        d["site"]["networking"]["ingress"] = {"engine": "caddy", "generate-upstream": False}
        p = policy(d)
        self.assertEqual(p["ingress"], "caddy")
        self.assertFalse(p["generate_upstream"])
        self.assertEqual(generate_caddyfile(d), "")
        self.assertEqual(generate_authelia(d), "")
        self.assertEqual(validate_placement(d), [])

    def test_background_image_is_not_rewritten_as_text(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "background.png"
            image.write_bytes(b"\xff\xd8\xff\xe0JFIF")
            note = Path(tmp) / "settings.yaml"
            note.write_text("title: Home\n", encoding="utf-8")
            self.assertIsNone(read_utf8(image))
            self.assertEqual(read_utf8(note), "title: Home\n")
            self.assertEqual(image.read_bytes(), b"\xff\xd8\xff\xe0JFIF")

    def test_authelia_file_backend(self) -> None:
        cfg = generate_authelia(self.desired)
        self.assertIn("file:", cfg)
        self.assertIn("/config/userdb/users.yml", cfg)
        self.assertIn("password_reset:", cfg)
        self.assertIn("policy: one_factor", cfg)
        self.assertIn("db.sqlite3", cfg)
        self.assertIn("oidc.pem", cfg)
        self.assertIn("claims_policies:", cfg)
        self.assertIn("client_id: opencloud", cfg)
        self.assertIn("oidc-silent-redirect.html", cfg)
        self.assertIn("consent_mode: implicit", cfg)
        self.assertIn("allowed_origins_from_client_redirect_uris: true", cfg)
        self.assertIn('secret "/config/userdb/oidc.pem"', cfg)
        self.assertNotIn("client_secret_digest", cfg)
        self.assertNotIn("address: ldap://openldap:389", cfg)

    def test_authelia_ldap_backend(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["identity"]["ldap"] = "openldap"
        d["site"]["hosts"][0]["operations"]["workload"]["services"]["openldap"] = None
        cfg = generate_authelia(d)
        self.assertIn("ldap:", cfg)
        self.assertIn("users_filter:", cfg)
        self.assertIn("groups_filter:", cfg)
        self.assertIn("objectClass=groupOfNames", cfg)
        self.assertIn(ldap_base_dn("example.lan"), cfg)
        self.assertIn("LDAP_ADMIN_PASSWORD", cfg)
        self.assertNotIn("dc=site,dc=lan", cfg)
        self.assertIn("password_reset:", cfg)
        self.assertIn("client_id: opencloud", cfg)
        self.assertIn("oidc-silent-redirect.html", cfg)
        self.assertIn("consent_mode: implicit", cfg)
        self.assertIn('secret "/config/userdb/oidc.pem"', cfg)
        self.assertNotIn("client_secret_digest", cfg)
        self.assertNotIn("path: /config/userdb/users.yml", cfg)

    def test_people_homes_follow_access(self) -> None:
        self.assertTrue(people_homes("smb", "none"))
        self.assertTrue(people_homes("none", "opencloud"))
        self.assertFalse(people_homes("none", "none"))
        self.assertTrue(build_plan(self.desired)["people_homes"])
        d = load_desired(EXAMPLE)
        d["site"]["data"]["access"]["filesystem"] = "none"
        d["site"]["data"]["access"]["web"] = "none"
        self.assertFalse(build_plan(d)["people_homes"])

    def test_directory_accounts_for_faiz_and_diana(self) -> None:
        desired = {
            "site": {
                "env": {"domain": "home.lan"},
                "data": {
                    "roots": {"users": "/users", "groups": "/groups"},
                    "access": {"filesystem": "smb", "web": "opencloud"},
                },
                "identity": {"ldap": "openldap", "sso": "authelia"},
                "users": [
                    {
                        "name": "faiz",
                        "roles": ["sysuser", "appadmin"],
                        "displayname": "Faiz",
                        "email": "faiz@home.lan",
                    },
                    {
                        "name": "diana",
                        "roles": ["sysuser", "appuser"],
                        "displayname": "Diana",
                        "email": "diana@home.lan",
                    },
                ],
                "hosts": [
                    {
                        "name": "core",
                        "ip": "192.168.1.110",
                        "operations": {"workload": {"services": {"openldap": None}}},
                    },
                    {"name": "mantle", "ip": "192.168.1.111", "operations": {"workload": {"services": {}}}},
                ],
            }
        }
        self.assertEqual(sso_groups(desired["site"]["users"][0]), ["users", "admins"])
        self.assertEqual(sso_groups(desired["site"]["users"][1]), ["users"])
        add, modify = build_ldif(desired, {"faiz": "pw-faiz", "diana": "pw-diana"})
        self.assertIn("uid=faiz,ou=users,dc=home,dc=lan", add)
        self.assertIn("uid=diana,ou=users,dc=home,dc=lan", add)
        self.assertIn("homeDirectory: /users/faiz", add)
        self.assertIn("homeDirectory: /users/diana", add)
        self.assertNotIn("userPassword", add)
        self.assertIn("userPassword: {SSHA}", modify)
        self.assertNotIn("pw-faiz", add + modify)
        self.assertNotIn("pw-diana", add + modify)
        admins = add.split("dn: cn=admins,ou=roles,dc=home,dc=lan", 1)[1].split("\n\n", 1)[0]
        self.assertIn("member: uid=faiz,ou=users,dc=home,dc=lan", admins)
        self.assertNotIn("diana", admins)
        users = add.split("dn: cn=users,ou=roles,dc=home,dc=lan", 1)[1].split("\n\n", 1)[0]
        self.assertIn("member: uid=faiz,ou=users,dc=home,dc=lan", users)
        self.assertIn("member: uid=diana,ou=users,dc=home,dc=lan", users)
        everyone = add.split("dn: cn=all,ou=groups,dc=home,dc=lan", 1)[1].split("\n\n", 1)[0]
        self.assertIn("memberUid: faiz", everyone)
        self.assertIn("memberUid: diana", everyone)
        self.assertIn("gidNumber: 20000", everyone)
        faiz = add.split("dn: uid=faiz,ou=users,dc=home,dc=lan", 1)[1].split("\n\n", 1)[0]
        self.assertIn("uidNumber: 20002", faiz)
        self.assertIn("gidNumber: 20000", faiz)
        core = render_sssd(desired, "core", "admin-pw")
        self.assertIn("ldap://127.0.0.1:1389", core)
        self.assertIn("ldap_search_base = dc=home,dc=lan", core)
        self.assertIn("ldap_user_search_base = ou=users,dc=home,dc=lan", core)
        self.assertIn("ldap_group_search_base = ou=groups,dc=home,dc=lan", core)
        self.assertIn("ldap_id_mapping = false", core)
        self.assertIn("ldap_default_bind_dn = cn=admin,dc=home,dc=lan", core)
        self.assertIn("ldap_default_authtok = admin-pw", core)
        self.assertNotIn("dc=site,dc=lan", core)
        remote = render_sssd(desired, "mantle", "admin-pw")
        self.assertIn("ldap://192.168.1.110:1389", remote)
        with self.assertRaises(SecretError):
            require_user_passwords(
                {"secrets": {"site": {"users": {"faiz": {"password": "x"}}}}},
                desired["site"]["users"],
            )

    def test_disjoint_sso_uses_the_site_password(self) -> None:
        import subprocess

        self.assertTrue(file_backend_needs_passwords(self.desired))
        hashed = authelia_password_hash("alice-secret")
        self.assertTrue(hashed.startswith("$6$"))
        salt = hashed.split("$")[2]
        check = subprocess.run(
            ["openssl", "passwd", "-6", "-stdin", "-salt", salt],
            input=b"alice-secret",
            capture_output=True,
            check=True,
        )
        self.assertEqual(check.stdout.decode().strip(), hashed)
        with self.assertRaises(SecretError):
            generate_authelia_users(self.desired)
        users = generate_authelia_users(self.desired, {"alice": "alice-secret", "bob": "bob-secret"})
        self.assertNotIn("alice-secret", users)
        self.assertNotIn("bob-secret", users)
        self.assertIn("$6$", users)
        self.assertIn("admins", users)
        ldap = load_desired(EXAMPLE)
        ldap["site"]["identity"]["ldap"] = "openldap"
        ldap["site"]["hosts"][0]["operations"]["workload"]["services"]["openldap"] = None
        self.assertFalse(file_backend_needs_passwords(ldap))
        unused = generate_authelia_users(ldap)
        self.assertIn("password: '*'", unused)
        self.assertNotIn("$6$", unused)

    def test_password_change_redeploys_edge(self) -> None:
        import tempfile

        left = Path(tempfile.mkdtemp()) / "secrets.yaml"
        right = Path(tempfile.mkdtemp()) / "secrets.yaml"
        text = "secrets:\n  site:\n    users:\n      alice:\n        password: {pw}\n"
        left.write_text(text.format(pw="one"), encoding="utf-8")
        right.write_text(text.format(pw="two"), encoding="utf-8")
        self.assertNotEqual(
            fingerprints(self.desired, left)["sections"]["edge"],
            fingerprints(self.desired, right)["sections"]["edge"],
        )
        self.assertEqual(
            fingerprints(self.desired, left)["sections"]["users"],
            fingerprints(self.desired, right)["sections"]["users"],
        )

    def test_authelia_ldap_password_env(self) -> None:
        unit = "[Container]\nEnvironment=TZ=UTC\n\n[Service]\nRestart=on-failure\n"
        out = inject_authelia_ldap_password(unit)
        self.assertIn(
            "Secret=${secrets.openldap.admin_password},type=env,target=LDAP_ADMIN_PASSWORD",
            out,
        )
        self.assertEqual(out.count("LDAP_ADMIN_PASSWORD"), 1)
        self.assertEqual(inject_authelia_ldap_password(out), out)

    def test_nfs_inferred_only_off_owner(self) -> None:
        nfs = inferred_nfs(self.desired)
        self.assertEqual(nfs["exports"], [])
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["operations"]["workload"]["services"]["immich"] = None
        nfs = inferred_nfs(d)
        paths = {e["path"] for e in nfs["exports"]}
        self.assertEqual(paths, {"/groups", "/users"})
        self.assertNotIn("/appdata", paths)
        self.assertTrue(all(e["client_ip"] == "10.0.0.11" for e in nfs["exports"]))

    def test_glances_pod_overlay_keeps_baseline(self) -> None:
        import yaml

        from .pod import apply_container_overlay

        base = (ROOT / "components" / "glances" / "glances.container").read_text(encoding="utf-8")
        overlay = yaml.safe_load(
            """
container:
  image: docker.io/nicolargo/glances:ubuntu-latest-full
  environment:
    NVIDIA_VISIBLE_DEVICES: "${host.resources.gpu.gpu0.uuid}"
    NVIDIA_DRIVER_CAPABILITIES: compute,utility
  addDevice:
    - "${host.resources.gpu.gpu0.resource}=all"
  volume:
    - /mnt/host/c:/mnt/windows:ro
"""
        )["container"]
        merged = apply_container_overlay(base, overlay)
        self.assertIn("Image=docker.io/nicolargo/glances:ubuntu-latest-full", merged)
        self.assertIn("Pull=always", merged)
        self.assertIn("Environment=TZ=${site.env.timezone}", merged)
        self.assertIn('Environment=GLANCES_OPT="-w --disable-plugin docker"', merged)
        self.assertIn(
            "Environment=NVIDIA_VISIBLE_DEVICES=${host.resources.gpu.gpu0.uuid}",
            merged,
        )
        self.assertIn("Environment=NVIDIA_DRIVER_CAPABILITIES=compute,utility", merged)
        self.assertIn("Volume=${host.data.roots.appdata}:/mnt/data:ro", merged)
        self.assertIn("Volume=/mnt/host/c:/mnt/windows:ro", merged)
        self.assertIn("AddDevice=${host.resources.gpu.gpu0.resource}=all", merged)
        host = self.desired["site"]["hosts"][1]
        rendered = render(merged, bind(self.desired, host))
        self.assertIn("docker.io/nicolargo/glances:ubuntu-latest-full", rendered)
        self.assertIn("AddDevice=nvidia.com/gpu=all", rendered)
        self.assertIn("/var/lib/site-appdata", rendered)
        self.assertIn("/mnt/host/c", rendered)
        self.assertIn("/mnt/data", rendered)
        untouched = apply_container_overlay(base, None)
        self.assertIn("Image=docker.io/nicolargo/glances:latest", untouched)

    def test_gpu_units_request_a_cdi_device(self) -> None:
        import yaml

        compute = bind(self.desired, self.desired["site"]["hosts"][1])
        immich = render((ROOT / "components" / "immich" / "pod.yaml").read_text(encoding="utf-8"), compute)
        pod = yaml.safe_load(immich)
        ml = next(c for c in pod["spec"]["containers"] if c["name"] == "immich-machine-learning")
        self.assertEqual(ml["resources"]["limits"]["nvidia.com/gpu=all"], 1)
        for name in ("jellyfin", "scriberr", "transmute"):
            unit = (ROOT / "components" / name / f"{name}.container").read_text(encoding="utf-8")
            self.assertIn("AddDevice=${host.resources.gpu.gpu0.resource}=all", unit)
            rendered = render(unit, compute)
            self.assertIn("AddDevice=nvidia.com/gpu=all", rendered)

    def test_opencloud_oidc_scope_stays_one_value(self) -> None:
        unit = (ROOT / "components" / "opencloud" / "opencloud.container").read_text(encoding="utf-8")
        self.assertIn('Environment=WEB_OIDC_SCOPE="openid groups profile email"', unit)

    def test_no_service_dir_without_qbit(self) -> None:
        plan = build_plan(self.desired)
        self.assertFalse(any(d["path"].endswith("/downloads") for d in plan["service_dirs"]))

    def test_inventory_uses_sysadmin(self) -> None:
        inv = inventory_dict(self.desired)
        self.assertEqual(inv["all"]["hosts"]["storage"]["ansible_user"], "admin")
        self.assertIn("storage", inv["all"]["children"]["storage"]["hosts"])
        self.assertIn("storage", inv["all"]["children"]["root_owners"]["hosts"])
        self.assertNotIn("compute", inv["all"]["children"]["root_owners"]["hosts"])

    def test_roots_are_sibling_binds(self) -> None:
        mounts = disk_mounts(self.desired)
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0]["where"], "/mnt/site/data")
        self.assertEqual(mounts[0]["unit"], "mnt-site-data.mount")
        binds = {b["root"]: b for b in root_binds(self.desired) if b["host"] == "storage"}
        self.assertEqual(binds["appdata"]["what"], "/mnt/site/data/appdata")
        self.assertEqual(binds["groups"]["what"], "/mnt/site/data/groups")
        self.assertEqual(binds["users"]["what"], "/mnt/site/data/users")
        self.assertEqual(binds["appdata"]["where"], "/appdata")
        self.assertEqual(binds["groups"]["where"], "/groups")
        self.assertEqual(binds["users"]["where"], "/users")
        self.assertTrue(all(b["kind"] == "bind" for b in binds.values()))

    def test_internal_disk_uses_slash(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["resources"]["disks"][0]["internal"] = True
        self.assertEqual(disk_mounts(d), [])
        binds = root_binds(d)
        self.assertTrue(all(b["kind"] == "dir" for b in binds))

    def test_local_roots_owned_on_internal_disk(self) -> None:
        locals_ = [b for b in root_binds(self.desired) if b["host"] == "compute"]
        self.assertEqual(len(locals_), 1)
        self.assertEqual(locals_[0]["kind"], "dir")
        self.assertEqual(locals_[0]["root"], "appdata")
        self.assertEqual(locals_[0]["where"], "/var/lib/site-appdata")
        self.assertEqual(validate_placement(self.desired), [])

    def test_local_roots_cannot_share_storage_disk(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["hosts"][0]["data"] = {"roots": {"scratch": "/scratch"}}
        bad["site"]["hosts"][0]["resources"]["disks"][0]["roots"] = ["scratch"]
        errs = validate_placement(bad)
        self.assertTrue(any("storage drive" in e for e in errs))

    def test_host_root_may_share_site_root_path(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["data"] = {"roots": {"appdata": "/appdata"}}
        errs = validate_placement(d)
        self.assertTrue(any("not owned" in e for e in errs))
        d["site"]["hosts"][0]["resources"]["disks"][0]["roots"] = ["appdata"]
        self.assertEqual(validate_placement(d), [])
        appdata = [b for b in root_binds(d) if b["host"] == "storage" and b["root"] == "appdata"]
        self.assertEqual(len(appdata), 1)
        self.assertEqual(appdata[0]["where"], "/appdata")
        self.assertEqual(appdata[0]["what"], "/mnt/site/data/appdata")
        mapping = bind(d, d["site"]["hosts"][0])
        self.assertEqual(mapping["host.data.roots.appdata"], "/appdata")

    def test_shared_site_path_does_not_depend_on_the_name(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["data"] = {"roots": {"local": "/appdata"}}
        d["site"]["hosts"][0]["resources"]["disks"][0]["roots"] = ["local"]
        self.assertEqual(validate_placement(d), [])
        self.assertEqual(
            [b for b in root_binds(d) if b["host"] == "storage" and b["root"] == "local"],
            [],
        )
        site = [b for b in root_binds(d) if b["host"] == "storage" and b["root"] == "appdata"]
        self.assertEqual(len(site), 1)
        mapping = bind(d, d["site"]["hosts"][0])
        self.assertEqual(mapping["host.data.roots.local"], "/appdata")
        self.assertNotIn("host.data.roots.appdata", mapping)

    def test_other_host_cannot_alias_site_root_path(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["data"] = {"roots": {"appdata": "/appdata"}}
        d["site"]["hosts"][1]["resources"]["disks"] = []
        errs = validate_placement(d)
        self.assertTrue(any("not owned" in e for e in errs))

    def test_local_roots_must_be_owned(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["hosts"][1]["data"]["roots"]["scratch"] = "/scratch"
        errs = validate_placement(bad)
        self.assertTrue(any("not owned" in e for e in errs))

    def test_local_root_mounts_non_internal_disk(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["data"] = {"roots": {"cache": "/var/cache/site"}}
        d["site"]["hosts"][1]["resources"]["disks"] = [
            {
                "id": "nvme",
                "uuid": "00000000-0000-0000-0000-000000000002",
                "roots": ["cache"],
            }
        ]
        mounts = {(m["host"], m["where"]) for m in disk_mounts(d)}
        self.assertIn(("compute", "/mnt/site/nvme"), mounts)
        bind = next(b for b in root_binds(d) if b["host"] == "compute" and b["root"] == "cache")
        self.assertEqual(bind["kind"], "bind")
        self.assertEqual(bind["what"], "/mnt/site/nvme/cache")
        self.assertEqual(bind["where"], "/var/cache/site")
        self.assertEqual(validate_placement(d), [])

    def test_partition_is_the_storage_drive(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["resources"]["disks"] = [
            {
                "id": "sda",
                "partitions": [
                    {
                        "id": "sda1",
                        "name": "ST4000NE001-2EN11C",
                        "size": "3.6T",
                        "uuid": "00000000-0000-0000-0000-000000000001",
                    }
                ],
            }
        ]
        d["site"]["hosts"][0]["operations"]["storage"]["drives"][0]["id"] = "sda1"
        mounts = disk_mounts(d)
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0]["where"], "/mnt/site/sda1")
        self.assertEqual(mounts[0]["uuid"], "00000000-0000-0000-0000-000000000001")
        binds = {b["root"]: b for b in root_binds(d) if b["host"] == "storage"}
        self.assertEqual(binds["users"]["what"], "/mnt/site/sda1/users")

    def test_internal_partition_owns_host_roots(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["data"] = {"roots": {"appdata": "/appdata"}}
        d["site"]["hosts"][1]["resources"]["disks"] = [
            {
                "id": "mmcblk0",
                "internal": True,
                "partitions": [
                    {"id": "mmcblk0p2", "uuid": "root-uuid", "roots": ["appdata"]},
                ],
            }
        ]
        self.assertFalse(any(m["host"] == "compute" for m in disk_mounts(d)))
        bind = next(b for b in root_binds(d) if b["host"] == "compute" and b["root"] == "appdata")
        self.assertEqual(bind["kind"], "dir")
        self.assertEqual(bind["where"], "/appdata")
        self.assertEqual(validate_placement(d), [])

    def test_typed_imports_ironwolf(self) -> None:
        d = load_desired(EXAMPLE)
        disk = d["site"]["hosts"][0]["resources"]["disks"][0]
        disk["id"] = "ironwolf"
        disk["import"] = [
            {"type": "user-home", "from": "/users/faiz"},
            {"type": "user-home", "from": "/users/diana"},
            {"type": "group-home", "from": "/shared", "to": "/all"},
            {"type": "appdata-home", "from": "/system/caddy"},
            {"type": "appdata-home", "from": "/system/homepage"},
            {"type": "appdata-home", "from": "/system/vaultwarden"},
            {"type": "appdata-home", "from": "/system/bytestash"},
        ]
        d["site"]["hosts"][0]["operations"]["storage"]["drives"][0]["id"] = "ironwolf"
        blocks = {b["from_rel"]: b for b in import_blocks(d)}
        self.assertEqual(blocks["/users/faiz"]["from"], "/mnt/site/ironwolf/users/faiz")
        self.assertEqual(blocks["/users/faiz"]["to"], "/users/faiz")
        self.assertTrue(blocks["/users/faiz"]["same_place"])
        self.assertEqual(blocks["/users/diana"]["to"], "/users/diana")
        self.assertEqual(blocks["/shared"]["to"], "/groups/all")
        self.assertEqual(blocks["/shared"]["from"], "/mnt/site/ironwolf/shared")
        self.assertFalse(blocks["/shared"]["same_place"])
        self.assertEqual(blocks["/system/caddy"]["to"], "/appdata/caddy")
        self.assertEqual(blocks["/system/caddy"]["from"], "/mnt/site/ironwolf/system/caddy")
        self.assertFalse(blocks["/system/caddy"]["same_place"])
        self.assertEqual(blocks["/system/homepage"]["to"], "/appdata/homepage")
        self.assertEqual(blocks["/system/vaultwarden"]["to"], "/appdata/vaultwarden")
        self.assertEqual(blocks["/system/bytestash"]["to"], "/appdata/bytestash")
        self.assertFalse(any(b["remote"] for b in blocks.values()))
        self.assertEqual(import_nfs(d), {"exports": [], "mounts": []})

    def test_import_as_relocates_home(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["resources"]["disks"][0]["import"] = [
            {"type": "group-home", "from": "/shared", "as": "/all"},
            {"type": "users-root", "from": "/users"},
        ]
        blocks = {b["type"]: b for b in import_blocks(d)}
        self.assertEqual(blocks["group-home"]["to"], "/groups/all")
        self.assertEqual(blocks["users-root"]["to"], "/users")
        self.assertEqual(blocks["users-root"]["from"], "/mnt/site/data/users")
        self.assertTrue(blocks["users-root"]["same_place"])

    def test_import_mapping_is_rejected(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["resources"]["disks"][0]["import"] = {"/shared": "/all"}
        with self.assertRaises(ValueError):
            import_blocks(d)

    def test_cross_host_import_uses_nfs(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["resources"] = {
            **(d["site"]["hosts"][1].get("resources") or {}),
            "disks": [
                {
                    "id": "old",
                    "uuid": "00000000-0000-0000-0000-000000000099",
                    "import": [{"type": "user-home", "from": "/users/faiz"}],
                }
            ],
        }
        blocks = import_blocks(d)
        self.assertEqual(blocks[0]["host"], "compute")
        self.assertEqual(blocks[0]["from"], "/mnt/site/old/users/faiz")
        self.assertEqual(blocks[0]["to"], "/users/faiz")
        self.assertTrue(blocks[0]["remote"])
        self.assertFalse(blocks[0]["same_place"])
        nfs = import_nfs(d)
        self.assertEqual({e["path"] for e in nfs["exports"]}, {"/users"})
        self.assertEqual(nfs["exports"][0]["host"], "storage")
        self.assertEqual(nfs["exports"][0]["client_ip"], "10.0.0.11")
        self.assertEqual(nfs["mounts"][0]["host"], "compute")
        self.assertEqual(nfs["mounts"][0]["path"], "/users")
        mounts = disk_mounts(d)
        self.assertEqual({(m["host"], m["where"]) for m in mounts}, {("storage", "/mnt/site/data"), ("compute", "/mnt/site/old")})

    def test_day2_delta(self) -> None:
        observed = {"services": [{"host": "storage", "name": "caddy"}], "users": [{"name": "alice"}]}
        sd = service_delta(self.desired, observed)
        self.assertTrue(sd["add"])
        ud = user_delta(self.desired, observed)
        self.assertIn("bob", ud["add"])
        self.assertEqual(ud["remove"], [])

    def test_day2_unchanged_set_touches_nothing(self) -> None:
        applied = fingerprints(self.desired)
        delta = set_delta(self.desired, applied)
        self.assertFalse(delta["full"])
        self.assertFalse(delta["sync_all"])
        self.assertFalse(any(delta["sections"].values()))
        self.assertEqual(delta["services"]["change"], [])
        self.assertEqual(delta["services"]["add"], [])

    def test_day2_homepage_edit_restarts_only_that_service(self) -> None:
        applied = fingerprints(self.desired)
        applied["services"]["storage/homepage"]["hash"] = "stale"
        delta = set_delta(self.desired, applied)
        names = {item["name"] for item in delta["services"]["change"]}
        self.assertEqual(names, {"homepage"})
        self.assertTrue(delta["sections"]["quadlets"])
        self.assertFalse(delta["sections"]["storage"])
        self.assertFalse(delta["sections"]["edge"])

    def test_authelia_unit_change_regenerates_edge(self) -> None:
        applied = fingerprints(self.desired)
        applied["services"]["storage/authelia"]["hash"] = "stale"
        delta = set_delta(self.desired, applied)
        names = {item["name"] for item in delta["services"]["change"]}
        self.assertIn("authelia", names)
        self.assertIn("caddy", names)
        self.assertTrue(delta["sections"]["edge"])

    def test_raw_env_secrets_restart_their_units(self) -> None:
        secrets = ROOT / "examples" / "secrets.example.yaml"
        applied = fingerprints(self.desired)
        delta = set_delta(self.desired, applied, secrets)
        names = {item["name"] for item in delta["services"]["change"]}
        self.assertIn("authelia", names)
        self.assertIn("homepage", names)
        self.assertNotIn("glances", names)
        self.assertTrue(delta["sections"]["secrets"])
        self.assertFalse(delta["sections"]["nfs"])
        self.assertFalse(delta["sections"]["admin_gui"])

    def test_storage_role_change_reruns_storage(self) -> None:
        applied = fingerprints(self.desired)
        role = ROOT / "ansible" / "roles" / "storage" / "tasks" / "main.yml"
        original = role.read_bytes()
        try:
            role.write_bytes(original + b"\n")
            delta = set_delta(self.desired, applied)
            self.assertTrue(delta["sections"]["storage"])
            self.assertFalse(delta["sections"]["admin_gui"])
        finally:
            role.write_bytes(original)

    def test_cockpit_role_change_reruns_admin_gui(self) -> None:
        applied = fingerprints(self.desired)
        role = ROOT / "ansible" / "roles" / "cockpit" / "tasks" / "main.yml"
        original = role.read_bytes()
        try:
            role.write_bytes(original + b"\n")
            delta = set_delta(self.desired, applied)
            self.assertTrue(delta["sections"]["admin_gui"])
            self.assertFalse(delta["sections"]["storage"])
        finally:
            role.write_bytes(original)

    def test_collabora_placement_rerenders_opencloud(self) -> None:
        applied = fingerprints(self.desired)
        current = load_desired(EXAMPLE)
        current["site"]["hosts"][0]["operations"]["workload"]["services"]["collabora"] = None
        delta = set_delta(current, applied)
        added = {item["key"] for item in delta["services"]["add"]}
        changed = {item["key"] for item in delta["services"]["change"]}
        self.assertIn("collabora", added)
        self.assertIn("opencloud", changed)

    def test_opencloud_integrations_follow_placement(self) -> None:
        import shutil
        import tempfile

        from .integrate import apply_placed_integrations

        def render_at(desired: dict, key: str) -> str:
            service = next(item for item in all_services(desired) if item["key"] == key)
            out = Path(tempfile.mkdtemp()) / service["name"]
            shutil.copytree(ROOT / "components" / service["component"], out)
            apply_placed_integrations(out, desired, service)
            return (out / f"{key}.container").read_text(encoding="utf-8")

        alone = render_at(self.desired, "opencloud")
        self.assertNotIn("COLLABORA_DOMAIN", alone)
        self.assertNotIn("OC_ADD_RUN_SERVICES", alone)
        proxy = (ROOT / "components" / "opencloud" / "proxy.yaml").read_text(encoding="utf-8")
        self.assertNotIn("caldav", proxy)

        both = load_desired(EXAMPLE)
        services = both["site"]["hosts"][0]["operations"]["workload"]["services"]
        services["collabora"] = {"subdomain": {"primary": "office"}}
        services["radicale"] = None
        cloud = render_at(both, "opencloud")
        self.assertIn("Environment=COLLABORA_DOMAIN=office.example.lan", cloud)
        self.assertIn("Environment=OC_ADD_RUN_SERVICES=collaboration", cloud)
        self.assertNotIn("COLLABORA_DOMAIN", render_at(self.desired, "opencloud"))
        office = render_at(both, "collabora")
        self.assertIn("Environment=aliasgroup1=https://opencloud.example.lan", office)
        self.assertIn("frame_ancestors=opencloud.example.lan", office)
        self.assertIn("lok_allow.host[14]=opencloud.example.lan", office)
        self.assertIn("ssl.termination=true", office)
        self.assertNotIn("ssl.ssl_termination", office)
        self.assertIn("ssl.ssl_verification=false", office)
        self.assertNotIn("CADDY_CA_URL", office)
        self.assertNotIn("Entrypoint=", office)
        self.assertIn("AddHost=opencloud.example.lan:169.254.1.2", office)
        self.assertIn('Environment=extra_params="--o:ssl.enable=false', office)
        self.assertIn("Environment=OC_URL=https://opencloud.example.lan", cloud)
        self.assertIn("Environment=IDP_DOMAIN=authelia.example.lan", cloud)
        self.assertIn("AddHost=authelia.example.lan:169.254.1.2", cloud)
        self.assertIn("AddHost=office.example.lan:169.254.1.2", cloud)
        self.assertNotIn("AddHost=office.example.lan:10.0.0.10", cloud)
        solo = load_desired(EXAMPLE)
        del solo["site"]["hosts"][0]["operations"]["workload"]["services"]["opencloud"]
        solo["site"]["hosts"][0]["operations"]["workload"]["services"]["collabora"] = None
        solo_office = render_at(solo, "collabora")
        self.assertNotIn("aliasgroup1", solo_office)
        self.assertIn("ssl.enable=false", solo_office)
        self.assertNotIn("frame_ancestors", solo_office)

        out = Path(tempfile.mkdtemp()) / "opencloud"
        shutil.copytree(ROOT / "components" / "opencloud", out)
        service = next(item for item in all_services(both) if item["key"] == "opencloud")
        apply_placed_integrations(out, both, service)
        routed = (out / "proxy.yaml").read_text(encoding="utf-8")
        self.assertIn("backend: http://radicale:5232", routed)
        self.assertFalse((out / "radicale-policy.yaml").exists())
        same_rad = render_at(both, "radicale")
        self.assertIn("PublishPort=127.0.0.1:5232:5232", same_rad)
        self.assertNotIn("PublishPort=${host.ip}:5232:5232", same_rad)

        split = load_desired(EXAMPLE)
        split["site"]["hosts"][1]["operations"]["workload"]["services"]["radicale"] = None
        split["site"]["hosts"][1]["operations"]["workload"]["services"]["collabora"] = {
            "subdomain": {"primary": "office"}
        }
        remote = Path(tempfile.mkdtemp()) / "opencloud"
        shutil.copytree(ROOT / "components" / "opencloud", remote)
        cloud_svc = next(item for item in all_services(split) if item["key"] == "opencloud")
        apply_placed_integrations(remote, split, cloud_svc)
        remote_unit = (remote / "opencloud.container").read_text(encoding="utf-8")
        self.assertIn("backend: http://10.0.0.11:5232", (remote / "proxy.yaml").read_text(encoding="utf-8"))
        self.assertIn("AddHost=office.example.lan:169.254.1.2", remote_unit)
        rad = Path(tempfile.mkdtemp()) / "radicale"
        shutil.copytree(ROOT / "components" / "radicale", rad)
        rad_svc = next(item for item in all_services(split) if item["key"] == "radicale")
        apply_placed_integrations(rad, split, rad_svc)
        rad_text = (rad / "radicale.container").read_text(encoding="utf-8")
        self.assertIn("PublishPort=127.0.0.1:5232:5232", rad_text)
        self.assertIn("PublishPort=${host.ip}:5232:5232", rad_text)
        far_office = render_at(split, "collabora")
        self.assertIn("AddHost=opencloud.example.lan:10.0.0.10", far_office)
        self.assertNotIn("169.254.1.2", far_office)

        moved = load_desired(EXAMPLE)
        del moved["site"]["hosts"][0]["operations"]["workload"]["services"]["opencloud"]
        moved["site"]["hosts"][1]["operations"]["workload"]["services"]["opencloud"] = {
            "subdomain": {"primary": "cloud"}
        }
        moved["site"]["hosts"][0]["operations"]["workload"]["services"]["collabora"] = {
            "subdomain": {"primary": "office"}
        }
        moved["site"]["hosts"][0]["operations"]["workload"]["services"]["authelia"] = {
            "subdomain": {"primary": "auth"}
        }
        near_office = render_at(moved, "collabora")
        self.assertIn("AddHost=cloud.example.lan:169.254.1.2", near_office)
        self.assertIn("AddHost=auth.example.lan:169.254.1.2", near_office)
        self.assertIn("aliasgroup1=https://cloud.example.lan", near_office)
        far_cloud = render_at(moved, "opencloud")
        self.assertIn("Environment=OC_URL=https://cloud.example.lan", far_cloud)
        self.assertIn("Environment=IDP_DOMAIN=auth.example.lan", far_cloud)
        self.assertIn("AddHost=auth.example.lan:10.0.0.10", far_cloud)
        self.assertIn("AddHost=office.example.lan:10.0.0.10", far_cloud)
        self.assertIn("Environment=COLLABORATION_WOPI_SRC=https://cloud.example.lan", far_cloud)
        self.assertIn("PublishPort=${host.ip}:9200:9200", far_cloud)

        caddy = generate_caddyfile(both)
        self.assertIn("https://radicale.example.lan", caddy)
        self.assertIn("import authelia_gate", caddy.split("https://radicale.example.lan {", 1)[1])
        self.assertIn("header_up X-Remote-User {http.request.header.Remote-User}", caddy)
        self.assertIn("reverse_proxy 127.0.0.1:5232", caddy)
        self.assertIn("reverse_proxy 127.0.0.1:9980", caddy)
        self.assertIn("read_timeout 3600s", caddy.split("https://office.example.lan {", 1)[1])
        remote_caddy = generate_caddyfile(split)
        self.assertIn("reverse_proxy 10.0.0.11:5232", remote_caddy)
        self.assertIn("reverse_proxy 10.0.0.11:9980", remote_caddy)

    def test_day2_new_web_service_updates_edge_only(self) -> None:
        applied = fingerprints(self.desired)
        current = load_desired(EXAMPLE)
        current["site"]["hosts"][0]["operations"]["workload"]["services"]["jotty"] = None
        delta = set_delta(current, applied)
        added = {item["name"] for item in delta["services"]["add"]}
        changed = {item["key"] for item in delta["services"]["change"]}
        self.assertIn("jotty", added)
        self.assertIn("caddy", changed)
        self.assertTrue(delta["sections"]["edge"])
        self.assertTrue(delta["sections"]["quadlets"])
        self.assertFalse(delta["sections"]["storage"])
        self.assertFalse(delta["sections"]["podman"])
        self.assertFalse(delta["sections"]["drivers"])

    def test_day2_without_stamp_skips_host_prep(self) -> None:
        delta = set_delta(self.desired, None, upgrade=True)
        self.assertFalse(delta["full"])
        self.assertTrue(delta["sync_all"])
        self.assertTrue(delta["sections"]["quadlets"])
        self.assertTrue(delta["sections"]["edge"])
        self.assertFalse(delta["sections"]["storage"])
        self.assertFalse(delta["sections"]["secrets"])
        self.assertFalse(delta["sections"]["podman"])

    def test_strip_k8s_kinds(self) -> None:
        text = "\n---\n".join(
            [
                "apiVersion: v1\nkind: Pod\nmetadata:\n  name: x\n  namespace: kube\nspec:\n  serviceAccountName: default\n  containers: []\n",
                "apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: i\n",
                "apiVersion: v1\nkind: Service\nmetadata:\n  name: s\n",
            ]
        )
        out = strip_yaml_text(text)
        self.assertIn("kind: Pod", out)
        self.assertNotIn("Ingress", out)
        self.assertNotIn("kind: Service", out)
        self.assertNotIn("serviceAccountName", out)
        self.assertNotIn("namespace:", out)

    def test_scaffold_uses_census_not_placeholders(self) -> None:
        observed = {
            "observed": {
                "hosts": [
                    {
                        "name": "core",
                        "ip": "192.168.1.110",
                        "mac": "00:e0:4c:68:04:21",
                        "os": {"name": "debian", "version": "13"},
                        "timezone": "America/Los_Angeles",
                        "locale": "en_GB.UTF-8",
                        "ssh": "key-only",
                        "ssh_user": "pilot",
                        "unix_users": [
                            {
                                "name": "pilot",
                                "uid": 1000,
                                "sysadmin": True,
                                "ssh_keys": ["ssh-rsa AAAATEST"],
                            }
                        ],
                        "pwm": "/sys/class/hwmon/hwmon3/pwm1",
                        "usb": [
                            {
                                "id": "1d6b:0002",
                                "bus": "002",
                                "device": "001",
                                "name": "Linux Foundation 2.0 root hub",
                            },
                            {
                                "id": "1a86:8091",
                                "bus": "002",
                                "device": "002",
                                "name": "QinHeng Electronics USB HUB",
                            },
                            {
                                "id": "0764:0501",
                                "bus": "002",
                                "device": "107",
                                "name": "Cyber Power System, Inc. CP1500 AVR UPS",
                            },
                            {
                                "id": "0bda:8156",
                                "bus": "005",
                                "device": "002",
                                "name": "Realtek Semiconductor Corp. USB 10/100/1G/2.5G LAN",
                            },
                        ],
                        "gpus": [],
                        "disks": [
                            {"name": "loop0", "type": "loop"},
                            {"name": "zram0", "type": "disk", "fstype": "swap"},
                            {
                                "name": "sda",
                                "type": "disk",
                                "size": "3.6T",
                                "tran": "sata",
                                "model": "ST4000NE001-2EN11C",
                                "children": [
                                    {
                                        "name": "sda1",
                                        "type": "part",
                                        "size": "3.6T",
                                        "fstype": "ext4",
                                        "uuid": "85b82a8e-4470-461b-8a8a-61f0d0ddd303",
                                    }
                                ],
                            },
                            {
                                "name": "mmcblk0",
                                "type": "disk",
                                "size": "29.1G",
                                "tran": "mmc",
                                "children": [
                                    {
                                        "name": "mmcblk0p1",
                                        "type": "part",
                                        "size": "512M",
                                        "fstype": "vfat",
                                        "uuid": "D8AB-6612",
                                        "mountpoint": "/boot/firmware",
                                    },
                                    {
                                        "name": "mmcblk0p2",
                                        "type": "part",
                                        "size": "28.6G",
                                        "fstype": "ext4",
                                        "uuid": "a7857f95-5305-411f-917d-93d06ca53dea",
                                        "mountpoint": "/",
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "name": "mantle",
                        "ip": "192.168.1.111",
                        "os": {"name": "ubuntu", "version": "26.04"},
                        "timezone": "America/Los_Angeles",
                        "locale": "C.UTF-8",
                        "ssh": "key-only",
                        "ssh_user": "pilot",
                        "unix_users": [{"name": "pilot", "uid": 1000, "ssh_keys": ["ssh-rsa AAAATEST"]}],
                        "gpus": [
                            "e012:00:00.0 3D controller: Microsoft Corporation Basic Render Driver"
                        ],
                        "disks": [
                            {"name": "sdd", "type": "disk", "size": "1T", "model": "Virtual Disk", "uuid": "2cdf487d-7d0a-4072-a64c-c22c6837e5de"}
                        ],
                    },
                ]
            }
        }
        text = scaffold_desired(observed)
        self.assertIn("name: core", text)
        self.assertIn("name: mantle", text)
        self.assertNotIn("host0", text)
        self.assertIn("name: pilot", text)
        self.assertNotIn("name: admin", text)
        self.assertIn("sysadmin: true", text)
        self.assertIn("sysadmin: false", text)
        self.assertNotIn("roles:", text)
        self.assertNotIn("example.lan", text)
        self.assertNotIn("cockpit", text)
        self.assertNotIn("glances", text)
        self.assertNotIn("podman", text)
        self.assertIn("ssh: key-only", text)
        self.assertLess(text.index("identity:"), text.index("hosts:"))
        self.assertLess(text.index("env:"), text.index("hosts:"))
        self.assertNotIn("override:", text)
        self.assertIn("timezone: America/Los_Angeles", text)
        self.assertIn("locale: en_GB.UTF-8", text)
        self.assertIn("locale: C.UTF-8", text)
        self.assertIn("85b82a8e-4470-461b-8a8a-61f0d0ddd303", text)
        self.assertIn("id: sda1", text)
        self.assertIn("ST4000NE001-2EN11C", text)
        self.assertIn("size: 3.6T", text)
        self.assertIn("id: mmcblk0p2", text)
        self.assertIn("size: 28.6G", text)
        self.assertNotIn("mmcblk0p1", text)
        self.assertNotIn("D8AB-6612", text)
        self.assertIn("Virtual Disk", text)
        self.assertIn("size: 1T", text)
        self.assertIn("internal: true", text)
        self.assertNotIn("loop0", text)
        self.assertNotIn("zram0", text)
        self.assertIn("2cdf487d-7d0a-4072-a64c-c22c6837e5de", text)
        self.assertNotIn("nvidia.com/gpu", text)
        self.assertIn("hwmon3/pwm1", text)
        self.assertIn("0764:0501", text)
        self.assertIn("usb:", text)
        self.assertIn("Cyber Power", text)
        self.assertNotIn("type: ups", text)
        self.assertNotIn("1d6b:0002", text)
        self.assertNotIn("1a86:8091", text)
        self.assertNotIn("0bda:8156", text)
        self.assertNotIn("Linux Foundation", text)
        self.assertNotIn("QinHeng", text)
        self.assertNotIn("Realtek", text)
        self.assertNotIn("lsusb:", text)

    def test_scaffold_disks_keeps_wsl_internal(self) -> None:
        disks = scaffold_disks(
            [
                {"name": "loop0", "type": "loop"},
                {"name": "sdc", "type": "disk", "model": "Virtual Disk", "fstype": "swap"},
                {"name": "sda", "type": "disk", "size": "356.9M", "model": "Virtual Disk", "fstype": "ext4"},
                {"name": "sdb", "type": "disk", "size": "159.4M", "model": "Virtual Disk", "fstype": "ext4"},
                {
                    "name": "sdd",
                    "type": "disk",
                    "size": "1T",
                    "model": "Virtual Disk",
                    "uuid": "2cdf487d-7d0a-4072-a64c-c22c6837e5de",
                    "fstype": "ext4",
                },
                {
                    "name": "sde",
                    "type": "disk",
                    "size": "3.6T",
                    "tran": "sata",
                    "model": "ST4000NE001-2EN11C",
                    "children": [
                        {"name": "sda1", "type": "part", "size": "3.6T", "fstype": "ext4", "uuid": "abc"},
                        {"name": "sda2", "type": "part", "fstype": "swap", "uuid": "swap-uuid"},
                    ],
                },
                {
                    "name": "mmcblk0",
                    "type": "disk",
                    "size": "29.1G",
                    "tran": "mmc",
                    "children": [
                        {
                            "name": "mmcblk0p1",
                            "type": "part",
                            "fstype": "vfat",
                            "uuid": "D8AB-6612",
                            "mountpoint": "/boot/firmware",
                        },
                        {
                            "name": "mmcblk0p2",
                            "type": "part",
                            "size": "28.6G",
                            "fstype": "ext4",
                            "uuid": "root-uuid",
                            "mountpoint": "/",
                        },
                    ],
                },
            ]
        )
        self.assertEqual(
            disks,
            [
                {
                    "id": "sdd",
                    "name": "Virtual Disk",
                    "size": "1T",
                    "uuid": "2cdf487d-7d0a-4072-a64c-c22c6837e5de",
                    "internal": True,
                },
                {
                    "id": "sde",
                    "partitions": [
                        {"id": "sda1", "name": "ST4000NE001-2EN11C", "size": "3.6T", "uuid": "abc"},
                    ],
                },
                {
                    "id": "mmcblk0",
                    "internal": True,
                    "partitions": [
                        {"id": "mmcblk0p2", "name": "mmcblk0p2", "size": "28.6G", "uuid": "root-uuid"},
                    ],
                },
            ],
        )
        ids = [d["id"] for d in disks]
        self.assertNotIn("sda", ids)
        self.assertNotIn("sdb", ids)

    def test_scaffold_nvidia_from_smi(self) -> None:
        observed = {
            "observed": {
                "hosts": [
                    {
                        "name": "mantle",
                        "ip": "192.168.1.111",
                        "os": {"name": "ubuntu", "version": "24.04"},
                        "gpus": ["GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-x)"],
                        "unix_users": [{"name": "pilot", "ssh_keys": []}],
                        "ssh_user": "pilot",
                    }
                ]
            }
        }
        text = scaffold_desired(observed)
        self.assertIn("id: gpu0", text)
        self.assertIn("NVIDIA GeForce RTX 2060", text)
        self.assertIn("GPU-x", text)
        self.assertIn("nvidia.com/gpu", text)
        self.assertNotIn("nvidia.com/gpu=all", text)
        self.assertEqual(text.count("id: gpu0"), 1)

    def test_scaffold_ignores_wsl_basic_render(self) -> None:
        observed = {
            "observed": {
                "hosts": [
                    {
                        "name": "mantle",
                        "ip": "192.168.1.111",
                        "gpus": [
                            "e012:00:00.0 3D controller: Microsoft Corporation Basic Render Driver",
                            "wsl-dxg: /dev/dxg present (Windows GPU; nvidia-smi not visible to this distro)",
                        ],
                    }
                ]
            }
        }
        self.assertNotIn("nvidia.com/gpu", scaffold_desired(observed))
        self.assertNotIn("gpu0", scaffold_desired(observed))

    def test_scaffold_ssh_override_when_hosts_differ(self) -> None:
        text = scaffold_desired(
            {
                "observed": {
                    "hosts": [
                        {"name": "core", "ssh": "key-only"},
                        {"name": "mantle", "ssh": "true"},
                    ]
                }
            }
        )
        self.assertNotIn("identity:\n    ssh:", text)
        self.assertIn("ssh: key-only", text)
        self.assertIn("ssh: 'true'", text)

    def test_scaffold_does_not_invent_admin(self) -> None:
        text = scaffold_desired({"observed": {"hosts": [{"name": "core", "ip": "10.0.0.1", "unix_users": []}]}})
        self.assertNotIn("admin", text)
        self.assertNotIn("users:", text)

    def test_lsusb_is_parsed_without_classifier(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("site_census", ROOT / "ansible" / "scripts" / "census.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        cps = mod.parse_lsusb_line(
            "Bus 002 Device 107: ID 0764:0501 Cyber Power System, Inc. CP1500 AVR UPS"
        )
        self.assertEqual(cps["id"], "0764:0501")
        self.assertEqual(cps["bus"], "002")
        self.assertEqual(cps["device"], "107")
        self.assertEqual(cps["name"], "Cyber Power System, Inc. CP1500 AVR UPS")
        self.assertNotIn("lsusb", cps)
        self.assertNotIn("type", cps)
        logi = mod.parse_lsusb_line("Bus 001 Device 005: ID 046d:c52b Logitech Unifying Receiver")
        self.assertEqual(logi["id"], "046d:c52b")
        self.assertIsNone(mod.parse_lsusb_line("not a usb line"))
        self.assertTrue(
            mod.usb_is_onboard({"id": "1a86:8091", "name": "QinHeng Electronics USB HUB"})
        )
        self.assertTrue(
            mod.usb_is_onboard({"id": "0bda:8156", "name": "Realtek Semiconductor Corp. USB 10/100/1G/2.5G LAN"})
        )
        self.assertFalse(
            mod.usb_is_onboard({"id": "0764:0501", "name": "Cyber Power System, Inc. CP1500 AVR UPS"})
        )
        self.assertFalse(mod.usb_is_onboard({"id": "0764:0501", "name": "CPS ST Series"}))
        sysfs_ups = mod.parse_sysfs_usb("0764", "0501", "CPS", "ST Series", "2", "31")
        self.assertEqual(sysfs_ups["id"], "0764:0501")
        self.assertEqual(sysfs_ups["bus"], "002")
        self.assertEqual(sysfs_ups["device"], "031")
        self.assertEqual(sysfs_ups["name"], "CPS ST Series")
        self.assertIsNone(mod.parse_sysfs_usb("", "0501"))
        merged = mod.merge_usb(
            [
                {"id": "1a86:8091", "name": "USB HUB"},
                {"id": "0764:0501", "name": "CPS ST Series", "bus": "002", "device": "031"},
                {
                    "id": "0764:0501",
                    "name": "Cyber Power System, Inc. CP1500 AVR UPS",
                    "bus": "002",
                    "device": "022",
                },
                {"id": "0bda:8156", "name": "Realtek USB 10/100/1G/2.5G LAN"},
            ]
        )
        self.assertEqual([u["id"] for u in merged], ["0764:0501"])
        self.assertEqual(merged[0]["name"], "Cyber Power System, Inc. CP1500 AVR UPS")
        sysfs_only = mod.merge_usb([{"id": "0764:0501", "name": "CPS ST Series"}])
        self.assertEqual(sysfs_only[0]["id"], "0764:0501")
        smi = mod.parse_nvidia_smi_line(
            "GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-1c085f37-5b85-9607-2a65-ff946d2af007)"
        )
        self.assertEqual(smi["id"], "gpu0")
        self.assertEqual(smi["name"], "NVIDIA GeForce RTX 2060")
        self.assertEqual(smi["uuid"], "GPU-1c085f37-5b85-9607-2a65-ff946d2af007")
        self.assertIsNone(
            mod.parse_nvidia_smi_line(
                "e012:00:00.0 3D controller: Microsoft Corporation Basic Render Driver"
            )
        )
        self.assertTrue(
            mod.nvidia_device_listed(["GPU 0: NVIDIA GeForce RTX 2060 (UUID: GPU-x)"])
        )
        self.assertFalse(
            mod.nvidia_device_listed(
                ["e012:00:00.0 3D controller: Microsoft Corporation Basic Render Driver"]
            )
        )
        self.assertFalse(mod.is_site_host_path("/mnt/c/Windows/System32/nvidia-smi.exe"))
        self.assertTrue(mod.is_site_host_path("/usr/lib/wsl/lib/nvidia-smi"))
        self.assertTrue(mod.user_is_sysadmin(["sudo"], ""))
        self.assertTrue(mod.user_is_sysadmin(["pilot"], "User pilot may run the following commands on core:\n    (ALL : ALL) ALL"))
        self.assertFalse(mod.user_is_sysadmin(["pilot"], "User testuser is not allowed to run sudo on mantle."))
        self.assertEqual(mod.ssh_policy_from_settings("no", "yes"), "key-only")
        self.assertEqual(mod.ssh_policy_from_settings("yes", "yes"), "true")

    def test_census_json_keeps_usb_name_with_comma(self) -> None:
        import base64
        import json

        census = {
            "hostname": "core",
            "usb": [
                {
                    "id": "0764:0501",
                    "bus": "002",
                    "device": "107",
                    "name": "Cyber Power System, Inc. CP1500 AVR UPS",
                }
            ],
        }
        observed = merge_observed(
            [{"census_b64": base64.b64encode(json.dumps(census).encode()).decode(), "ip": "10.0.0.10"}]
        )
        usb = observed["observed"]["hosts"][0]["usb"]
        self.assertEqual(usb[0]["name"], "Cyber Power System, Inc. CP1500 AVR UPS")
        self.assertEqual(usb[0]["id"], "0764:0501")
        mixed = merge_observed(
            [
                {
                    "census": {
                        "hostname": "core",
                        "usb": [
                            {"id": "1a86:8091", "name": "QinHeng Electronics USB HUB"},
                            {"id": "0764:0501", "name": "Cyber Power System, Inc. CP1500 AVR UPS"},
                            {"id": "0bda:8156", "name": "Realtek Semiconductor Corp. USB 10/100/1G/2.5G LAN"},
                        ],
                    }
                }
            ]
        )
        ids = [u["id"] for u in mixed["observed"]["hosts"][0]["usb"]]
        self.assertEqual(ids, ["0764:0501"])

    def test_pwm_duty_is_the_highest_source(self) -> None:
        from .pwm import hold_pwm, pwm_for_temp, target_pwm

        steps = [50, 70, 90, 110, 124]
        cpu = [60, 68, 75, 80, 85]
        disk = [40, 43, 46, 50, 55]
        self.assertEqual(pwm_for_temp(60, cpu, steps), 50)
        self.assertEqual(pwm_for_temp(64, cpu, steps), 60)
        self.assertEqual(pwm_for_temp(85, cpu, steps), 124)
        self.assertEqual(pwm_for_temp(90, cpu, steps), 124)
        self.assertEqual(pwm_for_temp(55, disk, steps), 124)
        scale = {
            "min": 0,
            "max": 124,
            "steps": steps,
            "sources": {"cpu": cpu, "disks": [{"sda": disk}]},
        }
        self.assertEqual(target_pwm({"cpu": 50, "disks.sda": 55}, scale), 124)
        self.assertEqual(target_pwm({"cpu": 61, "disks.sda": 30}, scale), 52)
        self.assertEqual(hold_pwm(67, 70, {"cpu": 67}, {"steps": steps, "sources": {"cpu": cpu}}), 70)
        self.assertEqual(hold_pwm(50, 70, {"cpu": 50}, {"steps": steps, "sources": {"cpu": cpu}}), 50)

    def test_pwm_kernel_trips_move_above_idle(self) -> None:
        import tempfile

        from .pwm import park_kernel_curve

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thermal = root / "thermal"
            zone = thermal / "thermal_zone0"
            other = thermal / "thermal_zone1"
            cdev = thermal / "cooling_device0"
            cdev.mkdir(parents=True)
            (cdev / "type").write_text("pwm-fan\n")
            zone.mkdir()
            other.mkdir()
            (zone / "cdev0").symlink_to(cdev, target_is_directory=True)
            (zone / "cdev0_trip_point").write_text("1\n")
            (zone / "trip_point_0_temp").write_text("110000\n")
            (zone / "trip_point_0_type").write_text("critical\n")
            (zone / "trip_point_1_temp").write_text("50000\n")
            (zone / "trip_point_1_type").write_text("active\n")
            (zone / "trip_point_2_temp").write_text("60000\n")
            (zone / "trip_point_2_type").write_text("active\n")
            (other / "trip_point_0_temp").write_text("50000\n")
            (other / "trip_point_0_type").write_text("active\n")
            hwmon = root / "hwmon3"
            hwmon.mkdir()
            (hwmon / "name").write_text("pwmfan\n")
            pwm = hwmon / "pwm1"
            pwm.write_text("0\n")

            self.assertTrue(park_kernel_curve(thermal, pwm))
            self.assertEqual((zone / "trip_point_0_temp").read_text().strip(), "110000")
            self.assertEqual((zone / "trip_point_1_temp").read_text().strip(), "105000")
            self.assertEqual((zone / "trip_point_2_temp").read_text().strip(), "105000")
            self.assertEqual((other / "trip_point_0_temp").read_text().strip(), "50000")
            self.assertFalse(park_kernel_curve(thermal, pwm))

            (hwmon / "name").write_text("drivetemp\n")
            (zone / "trip_point_1_temp").write_text("50000\n")
            self.assertFalse(park_kernel_curve(thermal, pwm))
            self.assertEqual((zone / "trip_point_1_temp").read_text().strip(), "50000")

    def test_pwm_scale_ceilings_must_match_steps(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][0]["resources"]["pwm"] = {
            "path": "/sys/class/hwmon/hwmon3/pwm1",
            "enabled": True,
            "scale": {
                "min": 0,
                "max": 124,
                "steps": [50, 70, 90, 110, 124],
                "sources": {
                    "cpu": [60, 68, 75, 80],
                    "disks": [{"nope": [40, 43, 46, 50, 55]}],
                },
            },
        }
        errs = validate_placement(d)
        self.assertTrue(any("cpu has 4 ceilings" in e for e in errs))
        self.assertTrue(any("disks.nope" in e for e in errs))
        d["site"]["hosts"][0]["resources"]["pwm"]["scale"]["sources"] = {
            "cpu": [60, 68, 75, 80, 85],
            "disks": [{"data": [40, 43, 46, 50, 55]}],
        }
        self.assertFalse(any("pwm scale" in e for e in validate_placement(d)))


class TestOpenCloudSpaces(unittest.TestCase):
    def test_personal_home_replaces_files_space_once(self) -> None:
        import tempfile

        from .opencloud_spaces import _set_xattr, apply_spaces, read_xattrs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            users = root / "users"
            groups = root / "groups"
            home = users / "faiz"
            files = home / "files"
            photos = home / "photos"
            shared = groups / "all"
            for path in (files, photos, shared):
                path.mkdir(parents=True)
            _set_xattr(files, "user.oc.id", b"42c0c762-7a1e-4bf4-851f-7fa334f93bac")
            _set_xattr(files, "user.oc.space.id", b"42c0c762-7a1e-4bf4-851f-7fa334f93bac")
            _set_xattr(files, "user.oc.space.type", b"personal")
            _set_xattr(files, "user.oc.space.alias", b"personal/faiz")
            _set_xattr(files, "user.oc.name", b"files")
            _set_xattr(photos, "user.oc.id", b"5b480a4e-82cc-4e9b-8015-eb0bd711fa9c")
            _set_xattr(photos, "user.oc.space.id", b"5b480a4e-82cc-4e9b-8015-eb0bd711fa9c")
            _set_xattr(photos, "user.oc.space.type", b"project")
            _set_xattr(photos, "user.oc.grant.u:old", b"stale")
            blob = root / "idm"
            blob.write_bytes(b"uid=faiz,ou=users,o=libregraph-idm openCloudUUID b251124a-1a13-4ef0-ab80-faf45d54dd45")
            spec = {
                "users_root": str(users),
                "groups_root": str(groups),
                "idm": str(blob),
                "idp": "https://auth.example.lan",
                "users": [{"name": "faiz", "displayname": "Faiz"}],
                "groups": ["all"],
            }
            scans = apply_spaces(spec)
            self.assertEqual(scans, ["/posix/users/faiz", "/posix/groups/all"])
            home_attrs = read_xattrs(home)
            self.assertEqual(home_attrs["user.oc.space.type"], b"personal")
            self.assertEqual(home_attrs["user.oc.space.alias"], b"personal/faiz")
            self.assertEqual(home_attrs["user.oc.owner.id"], home_attrs["user.oc.id"])
            self.assertEqual(home_attrs["user.oc.owner.type"], b"spaceowner")
            self.assertIn("user.oc.grant.u:b251124a-1a13-4ef0-ab80-faf45d54dd45", home_attrs)
            files_attrs = read_xattrs(files)
            self.assertNotIn("user.oc.space.type", files_attrs)
            self.assertEqual(files_attrs["user.oc.id"], b"42c0c762-7a1e-4bf4-851f-7fa334f93bac")
            self.assertEqual(files_attrs["user.oc.parentid"], home_attrs["user.oc.id"])
            self.assertNotIn("user.oc.space.type", read_xattrs(photos))
            self.assertNotIn("user.oc.grant.u:old", read_xattrs(photos))
            group_attrs = read_xattrs(shared)
            self.assertEqual(group_attrs["user.oc.space.type"], b"project")
            self.assertEqual(group_attrs["user.oc.space.alias"], b"project/all")
            self.assertIn("user.oc.grant.u:b251124a-1a13-4ef0-ab80-faf45d54dd45", group_attrs)
            self.assertEqual(apply_spaces(spec), [])

    def test_user_id_ignores_group_membership_records(self) -> None:
        from .opencloud_spaces import oc_uuid

        blob = (
            b"uid=faiz,ou=users,o=libregraph-idm\x00displayName\x00openCloudUUID\x00"
            b"$b251124a-1a13-4ef0-ab80-faf45d54dd45"
            b"\x00#cn=users,ou=groups,o=libregraph-idm\x00openCloudUUID\x00"
            b"$b5318a1a-50af-4cb6-90b6-dddfd7b3e469"
            b"\x00uid=faiz,ou=users,o=libregraph-idm\x00$cn=admins,ou=groups\x00openCloudUUID\x00"
            b"$c97ace90-fc46-4340-b4d8-9f18bc60ca92"
        )
        self.assertEqual(oc_uuid(blob, "faiz"), "b251124a-1a13-4ef0-ab80-faf45d54dd45")
        self.assertIsNone(oc_uuid(blob, "diana"))

    def test_wrong_owner_is_relinked_and_indexed_once(self) -> None:
        import tempfile

        from .opencloud_spaces import _set_xattr, apply_spaces, read_xattrs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "users" / "faiz"
            shared = root / "groups" / "all"
            home.mkdir(parents=True)
            shared.mkdir(parents=True)
            space = b"6d4c951b-cf47-4064-9f0f-4ee94b6e318e"
            _set_xattr(home, "user.oc.id", space)
            _set_xattr(home, "user.oc.space.id", space)
            _set_xattr(home, "user.oc.space.type", b"personal")
            _set_xattr(home, "user.oc.space.alias", b"personal/faiz")
            _set_xattr(home, "user.oc.owner.id", b"c97ace90-fc46-4340-b4d8-9f18bc60ca92")
            _set_xattr(home, "user.oc.owner.type", b"primary")
            group = b"1b01aa68-994f-4c43-8f46-cee6a31f3100"
            _set_xattr(shared, "user.oc.id", group)
            _set_xattr(shared, "user.oc.space.id", group)
            _set_xattr(shared, "user.oc.space.type", b"project")
            _set_xattr(shared, "user.oc.space.alias", b"project/all")
            _set_xattr(shared, "user.oc.grant.u:c97ace90-fc46-4340-b4d8-9f18bc60ca92", b"stale")
            blob = root / "idm"
            blob.write_bytes(
                b"uid=faiz,ou=users,o=libregraph-idm\x00openCloudUUID\x00"
                b"b251124a-1a13-4ef0-ab80-faf45d54dd45"
                b"\x00cn=admins,ou=groups\x00openCloudUUID\x00"
                b"c97ace90-fc46-4340-b4d8-9f18bc60ca92"
                b"\x00uid=faiz,ou=users,o=libregraph-idm"
            )
            spec = {
                "users_root": str(root / "users"),
                "groups_root": str(root / "groups"),
                "idm": str(blob),
                "idp": "https://auth.example.lan",
                "users": [{"name": "faiz", "displayname": "Faiz"}],
                "groups": ["all"],
            }
            self.assertEqual(apply_spaces(spec), [])
            self.assertEqual(read_xattrs(home)["user.oc.owner.id"], space)
            self.assertEqual(read_xattrs(home)["user.oc.owner.type"], b"spaceowner")
            self.assertEqual(read_xattrs(home)["user.oc.id"], space)
            group_attrs = read_xattrs(shared)
            self.assertEqual(group_attrs["user.oc.id"], group)
            self.assertIn("user.oc.grant.u:b251124a-1a13-4ef0-ab80-faf45d54dd45", group_attrs)
            self.assertNotIn("user.oc.grant.u:c97ace90-fc46-4340-b4d8-9f18bc60ca92", group_attrs)
            self.assertEqual(apply_spaces(spec), [])

    def test_space_index_lists_personal_and_group_once(self) -> None:
        import tempfile

        from .opencloud_spaces import _load_index, apply_spaces

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "users" / "faiz").mkdir(parents=True)
            (root / "groups" / "all").mkdir(parents=True)
            blob = root / "idm"
            blob.write_bytes(
                b"uid=faiz,ou=users,o=libregraph-idm\x00openCloudUUID\x00"
                b"b251124a-1a13-4ef0-ab80-faf45d54dd45"
            )
            spec = {
                "users_root": str(root / "users"),
                "groups_root": str(root / "groups"),
                "indexes": str(root / "indexes"),
                "idm": str(blob),
                "idp": "https://auth.example.lan",
                "users": [{"name": "faiz", "displayname": "Faiz"}],
                "groups": ["all"],
            }
            self.assertEqual(apply_spaces(spec), ["/posix/users/faiz", "/posix/groups/all"])
            user_index = _load_index(root / "indexes" / "by-user-id" / "b251124a-1a13-4ef0-ab80-faf45d54dd45.mpk")
            personal = next(iter(user_index))
            self.assertEqual(user_index[personal], personal)
            self.assertEqual(len(user_index), 2)
            self.assertEqual(_load_index(root / "indexes" / "by-type" / "personal.mpk"), {personal: personal})
            project = next(space for space in user_index if space != personal)
            self.assertEqual(_load_index(root / "indexes" / "by-type" / "project.mpk"), {project: project})
            self.assertEqual(apply_spaces(spec), [])

    def test_homes_converge_from_missing_stale_and_current_xattrs(self) -> None:
        import tempfile

        from .opencloud_spaces import LIST_ROLE, _grant_bytes, _set_xattr, apply_spaces, read_xattrs

        faiz = "b251124a-1a13-4ef0-ab80-faf45d54dd45"
        stale = "c97ace90-fc46-4340-b4d8-9f18bc60ca92"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bare = root / "users" / "faiz"
            (bare / "files").mkdir(parents=True)
            (bare / "photos").mkdir()
            shared = root / "groups" / "all"
            (shared / "media").mkdir(parents=True)
            blob = root / "idm"
            blob.write_bytes(f"uid=faiz,ou=users,o=libregraph-idm\x00openCloudUUID\x00{faiz}".encode())
            spec = {
                "users_root": str(root / "users"),
                "groups_root": str(root / "groups"),
                "idm": str(blob),
                "users": [{"name": "faiz", "displayname": "Faiz"}],
                "groups": ["all"],
            }
            self.assertEqual(apply_spaces(spec), ["/posix/users/faiz", "/posix/groups/all"])
            home_attrs = read_xattrs(bare)
            self.assertEqual(home_attrs["user.oc.owner.type"], b"spaceowner")
            self.assertEqual(home_attrs["user.oc.owner.id"], home_attrs["user.oc.id"])
            self.assertEqual(home_attrs[f"user.oc.grant.u:{faiz}"], _grant_bytes(f"u:{faiz}", LIST_ROLE))
            self.assertEqual(
                read_xattrs(bare / "files")[f"user.oc.grant.u:{faiz}"],
                _grant_bytes(f"u:{faiz}", "txrwaduUq"),
            )
            self.assertEqual(
                read_xattrs(shared / "media")[f"user.oc.grant.u:{faiz}"],
                _grant_bytes(f"u:{faiz}", "txrwaduUq"),
            )

            space = home_attrs["user.oc.id"]
            _set_xattr(bare, f"user.oc.grant.u:{stale}", b"stale")
            _set_xattr(bare / "files", f"user.oc.grant.u:{stale}", b"stale")
            self.assertEqual(apply_spaces(spec), [])
            self.assertNotIn(f"user.oc.grant.u:{stale}", read_xattrs(bare))
            self.assertNotIn(f"user.oc.grant.u:{stale}", read_xattrs(bare / "files"))
            self.assertEqual(read_xattrs(bare)["user.oc.id"], space)
            kept = read_xattrs(bare)["user.oc.mtime"]
            self.assertEqual(apply_spaces(spec), [])
            self.assertEqual(read_xattrs(bare)["user.oc.mtime"], kept)


class TestWireGuardHelper(unittest.TestCase):
    def setUp(self) -> None:
        import importlib.util
        from importlib.machinery import SourceFileLoader

        path = ROOT / "components" / "wg-easy" / "site-wg-helper"
        loader = SourceFileLoader("site_wg_helper", str(path))
        spec = importlib.util.spec_from_loader("site_wg_helper", loader)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        self.helper = module
        self.bins = {
            "wg": "/usr/bin/wg",
            "ip": "/usr/sbin/ip",
            "iptables": "/usr/sbin/iptables-nft",
        }

    def _key(self, seed: int) -> str:
        import base64

        return base64.b64encode(bytes((seed + i) % 256 for i in range(32))).decode()

    def _conf(self) -> str:
        hook = "PostUp = /bin/sh -c id"
        return (
            "[Interface]\n"
            "Address = 10.8.0.1/24\n"
            "ListenPort = 51820\n"
            f"PrivateKey = {self._key(1)}\n"
            "MTU = 1280\n"
            f"{hook}\n"
            "\n[Peer]\n"
            f"PublicKey = {self._key(2)}\n"
            "AllowedIPs = 10.8.0.2/32\n"
        )

    def _runner(self, calls: list[list[str]], seen: dict[str, str]):
        def runner(argv: list[str], stdin: bytes) -> tuple[int, bytes, bytes]:
            calls.append(argv)
            if argv[1:4] == ["link", "show", "dev"]:
                return 1, b"", b""
            if argv[1:4] == ["-4", "route", "get"]:
                return 0, b"1.1.1.1 via 192.0.2.1 dev eth1 src 192.0.2.10\n", b""
            if argv[1:4] == ["-t", "nat", "-S"]:
                return 0, b"-A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE\n", b""
            if len(argv) >= 2 and argv[1] in {"setconf", "syncconf"}:
                seen["body"] = Path(argv[-1]).read_text(encoding="utf-8")
                seen["path"] = argv[-1]
            if "-C" in argv:
                return 1, b"", b""
            return 0, b"", b""

        return runner

    def test_show_is_dump_only(self) -> None:
        calls: list[list[str]] = []

        def runner(argv: list[str], stdin: bytes) -> tuple[int, bytes, bytes]:
            calls.append(argv)
            return 0, b"dump\n", b""

        result = self.helper.evaluate({"op": "show", "iface": "wg0"}, "/tmp", runner, self.bins)
        self.assertEqual(result["code"], 0)
        self.assertEqual(calls, [["/usr/bin/wg", "show", "wg0", "dump"]])
        rejected = self.helper.evaluate({"op": "show", "iface": "../etc"}, "/tmp", runner, self.bins)
        self.assertEqual(rejected["code"], 1)
        self.assertEqual(len(calls), 1)

    def test_up_drops_hooks_and_builds_nat(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "wg0.conf").write_text(self._conf(), encoding="utf-8")
            calls: list[list[str]] = []
            seen: dict[str, str] = {}
            result = self.helper.evaluate(
                {"op": "up", "iface": "wg0"},
                tmp,
                self._runner(calls, seen),
                self.bins,
            )
            self.assertEqual(result["code"], 0, result)
            self.assertNotIn("PostUp", seen["body"])
            self.assertNotIn("/bin/sh", seen["body"])
            self.assertIn(f"PrivateKey = {self._key(1)}", seen["body"])
            self.assertIn("AllowedIPs = 10.8.0.2/32", seen["body"])
            self.assertFalse(Path(seen["path"]).exists())
            flat = [" ".join(call) for call in calls]
            self.assertTrue(any(item.endswith(" wg setconf wg0 " + seen["path"]) or "setconf wg0" in item for item in flat))
            self.assertIn(
                "/usr/sbin/iptables-nft -t nat -D POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE",
                flat,
            )
            self.assertIn(
                "/usr/sbin/iptables-nft -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth1 -j MASQUERADE",
                flat,
            )
            self.assertIn("/usr/sbin/iptables-nft -I FORWARD 1 -i wg0 -j ACCEPT", flat)
            self.assertIn("/usr/sbin/iptables-nft -I FORWARD 1 -o wg0 -j ACCEPT", flat)
            self.assertIn(
                "/usr/sbin/iptables-nft -t mangle -A FORWARD -i wg0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1240",
                flat,
            )
            self.assertIn(
                "/usr/sbin/iptables-nft -t mangle -A FORWARD -o wg0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1240",
                flat,
            )
            self.assertFalse(any("/bin/sh" in item or "PostUp" in item for item in flat))

    def test_sync_rebuilds_peer_file(self) -> None:
        import tempfile

        text = (
            "[Interface]\n"
            f"PrivateKey = {self._key(1)}\n"
            "ListenPort = 51820\n"
            "PostUp = iptables -F\n"
            "\n[Peer]\n"
            f"PublicKey = {self._key(2)}\n"
            "AllowedIPs = 10.8.0.2/32\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            calls: list[list[str]] = []
            seen: dict[str, str] = {}
            result = self.helper.evaluate(
                {"op": "sync", "iface": "wg0", "config": text},
                tmp,
                self._runner(calls, seen),
                self.bins,
            )
            self.assertEqual(result["code"], 0, result)
            self.assertNotIn("PostUp", seen["body"])
            self.assertNotIn("iptables", seen["body"])
            self.assertIn("PublicKey = ", seen["body"])
            self.assertFalse(Path(seen["path"]).exists())
            self.assertTrue(any("syncconf" in " ".join(call) for call in calls))

    def test_raw_commands_are_rejected(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            calls: list[list[str]] = []
            seen: dict[str, str] = {}
            runner = self._runner(calls, seen)
            blocked = self.helper.evaluate(
                {"cmd": "iptables", "args": ["-F"]},
                tmp,
                runner,
                self.bins,
            )
            self.assertEqual(blocked["code"], 127)
            self.assertEqual(calls, [])
            foreign = self.helper.evaluate({"op": "genkey"}, tmp, runner, self.bins)
            self.assertEqual(foreign["code"], 127)
            self.assertEqual(calls, [])

    def test_node_client_rejects_iptables_and_sends_show(self) -> None:
        import os
        import shutil
        import socket
        import subprocess
        import tempfile
        import threading

        if shutil.which("node") is None:
            self.skipTest("node is not installed")
        script = ROOT / "components" / "wg-easy" / "handoff" / "handoff.mjs"
        refused = subprocess.run(
            ["node", str(script), "iptables", "-F"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(refused.returncode, 127)
        self.assertIn(b"rejected command", refused.stderr)
        shell = (ROOT / "components" / "wg-easy" / "handoff" / "handoff.sh").read_text(encoding="utf-8")
        self.assertIn('exec /usr/bin/wg "$@"', shell)
        with tempfile.TemporaryDirectory() as tmp:
            sock_path = os.path.join(tmp, "helper.sock")
            ready = threading.Event()

            def serve() -> None:
                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(sock_path)
                os.chmod(sock_path, 0o666)
                server.listen(1)
                server.settimeout(5)
                ready.set()
                conn, _addr = server.accept()
                self.helper.handle_client(conn, 1000, 1000, tmp)
                server.close()

            thread = threading.Thread(target=serve)
            thread.start()
            self.assertTrue(ready.wait(2))
            env = os.environ.copy()
            env["WG_HELPER_SOCK"] = sock_path
            shown = subprocess.run(
                ["node", str(script), "wg", "show", "wg0", "dump"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=env,
                timeout=5,
                check=False,
            )
            thread.join(5)
            self.assertNotEqual(shown.returncode, 127)
            self.assertNotIn(b"rejected command", shown.stderr)


if __name__ == "__main__":
    unittest.main()
