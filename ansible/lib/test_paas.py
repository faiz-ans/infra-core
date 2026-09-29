"""Unit tests for topology, resolver, generators, plan, and Quadlet strip."""
from __future__ import annotations

import unittest
from pathlib import Path

from .diff import service_delta, user_delta
from .observed import merge_observed, scaffold_desired, scaffold_disks
from .generate import generate_authelia, generate_caddyfile, generate_homepage_services
from .inventory import inventory_dict
from .plan import build_plan, disk_mounts, import_blocks, import_nfs, inferred_nfs, root_binds
from .quadlet import strip_yaml_text
from .resolve import LOOPBACK, bind, render
from .secrets import SecretError, podman_catalog, resolve_secret, split_secrets
from .topology import (
    all_services,
    key_only_ready,
    load_desired,
    validate_placement,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "site.example.yaml"


class TestExample(unittest.TestCase):
    def setUp(self) -> None:
        self.desired = load_desired(EXAMPLE)

    def test_placement_ok(self) -> None:
        self.assertEqual(validate_placement(self.desired), [])

    def test_implicit_glances_on_storage_host(self) -> None:
        keys = {(s["host"], s["key"]) for s in all_services(self.desired)}
        self.assertIn(("storage", "glances"), keys)
        self.assertIn(("compute", "glances"), keys)

    def test_openldap_must_be_placed(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["identity"]["ldap"] = "openldap"
        errs = validate_placement(bad)
        self.assertTrue(any("openldap" in e for e in errs))

    def test_two_caddy_is_error(self) -> None:
        bad = load_desired(EXAMPLE)
        bad["site"]["hosts"][1]["roles"]["workload"]["services"]["caddy"] = None
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
        self.assertEqual(m["site.networking.loopback"], LOOPBACK)
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
        self.assertEqual(
            render("${host.data.roots.appdata}/caddy", compute),
            "/var/lib/site-appdata/caddy",
        )
        self.assertNotIn("host.data.roots.appdata", storage)

    def test_caddy_and_homepage(self) -> None:
        caddy = generate_caddyfile(self.desired)
        self.assertIn("auth.example.lan", caddy)
        self.assertIn("cloud.example.lan", caddy)
        home = generate_homepage_services(self.desired)
        self.assertIn(LOOPBACK, home)
        self.assertIn("HOMEPAGE_VAR_PIHOLE_TOKEN", home)

    def test_generate_flags_off(self) -> None:
        from .topology import policy

        d = load_desired(EXAMPLE)
        d["site"]["networking"]["ingress"] = {"engine": "caddy", "generate-upstream": False}
        d["site"]["operations"]["dashboard"] = {"engine": "homepage", "generate-tiles": False}
        p = policy(d)
        self.assertEqual(p["ingress"], "caddy")
        self.assertFalse(p["generate_upstream"])
        self.assertFalse(p["generate_tiles"])
        self.assertEqual(generate_caddyfile(d), "")
        self.assertEqual(generate_authelia(d), "")
        self.assertEqual(generate_homepage_services(d), "")
        self.assertEqual(validate_placement(d), [])

    def test_authelia_file_backend(self) -> None:
        cfg = generate_authelia(self.desired)
        self.assertIn("file:", cfg)
        self.assertIn("claims_policies:", cfg)
        self.assertIn("opencloud", cfg)

    def test_authelia_ldap_backend(self) -> None:
        d = load_desired(EXAMPLE)
        d["site"]["identity"]["ldap"] = "openldap"
        d["site"]["hosts"][0]["roles"]["workload"]["services"]["openldap"] = None
        cfg = generate_authelia(d)
        self.assertIn("ldap:", cfg)

    def test_nfs_inferred_only_off_owner(self) -> None:
        nfs = inferred_nfs(self.desired)
        self.assertEqual(nfs["exports"], [])
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["roles"]["workload"]["services"]["immich"] = None
        nfs = inferred_nfs(d)
        paths = {e["path"] for e in nfs["exports"]}
        self.assertEqual(paths, {"/groups", "/users"})
        self.assertNotIn("/appdata", paths)
        self.assertTrue(all(e["client_ip"] == "10.0.0.11" for e in nfs["exports"]))

    def test_glances_pod_overlay_keeps_baseline(self) -> None:
        import yaml

        from .pod import merge_pod
        from .quadlet import strip_yaml_text

        base = yaml.safe_load((ROOT / "components" / "glances" / "pod.yaml").read_text())
        overlay = yaml.safe_load(
            """
pod:
  spec:
    containers:
    - name: glances
      image: docker.io/nicolargo/glances:ubuntu-latest-full
      env:
      - name: NVIDIA_VISIBLE_DEVICES
        value: "${host.resources.gpu.gpu0.uuid}"
      - name: NVIDIA_DRIVER_CAPABILITIES
        value: compute,utility
      resources:
        limits:
          ${host.resources.gpu.gpu0.resource}: 1
      volumeMounts:
      - name: win
        mountPath: /mnt/windows
        readOnly: true
    volumes:
    - name: win
      hostPath:
        path: /mnt/host/c
"""
        )["pod"]
        merged = merge_pod(base, overlay)
        container = merged["spec"]["containers"][0]
        self.assertEqual(container["image"], "docker.io/nicolargo/glances:ubuntu-latest-full")
        self.assertEqual(container["imagePullPolicy"], "Always")
        env = {item["name"]: item["value"] for item in container["env"]}
        self.assertEqual(env["TZ"], "${site.env.timezone}")
        self.assertEqual(env["GLANCES_OPT"], "-w --disable-plugin docker")
        self.assertEqual(
            env["NVIDIA_VISIBLE_DEVICES"],
            "${host.resources.gpu.gpu0.uuid}",
        )
        mounts = {item["name"] for item in container["volumeMounts"]}
        self.assertEqual(mounts, {"conf", "osrel", "sys", "data", "win"})
        vols = {item["name"]: item["hostPath"]["path"] for item in merged["spec"]["volumes"]}
        self.assertEqual(vols["data"], "${host.data.roots.appdata}")
        self.assertEqual(vols["win"], "/mnt/host/c")
        self.assertEqual(container["resources"]["limits"]["${host.resources.gpu.gpu0.resource}"], 1)
        host = self.desired["site"]["hosts"][1]
        rendered = render(yaml.safe_dump(merged, sort_keys=False), bind(self.desired, host))
        stripped = strip_yaml_text(rendered)
        self.assertIn("docker.io/nicolargo/glances:ubuntu-latest-full", stripped)
        self.assertIn("nvidia.com/gpu: 1", stripped)
        self.assertIn("/var/lib/site-appdata", stripped)
        self.assertIn("/mnt/host/c", stripped)
        self.assertIn("/mnt/data", stripped)
        untouched = merge_pod(base, None)
        self.assertEqual(untouched["spec"]["containers"][0]["image"], "docker.io/nicolargo/glances:latest")

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
        d["site"]["hosts"][0]["roles"]["storage"]["drives"][0]["id"] = "sda1"
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
        d["site"]["hosts"][0]["roles"]["storage"]["drives"][0]["id"] = "ironwolf"
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


if __name__ == "__main__":
    unittest.main()
