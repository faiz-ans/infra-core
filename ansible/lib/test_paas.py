"""Unit tests for topology, resolver, generators, plan, and Quadlet strip."""
from __future__ import annotations

import unittest
from pathlib import Path

from .diff import service_delta, user_delta
from .generate import generate_authelia, generate_caddyfile, generate_homepage_services
from .inventory import inventory_dict
from .plan import build_plan, inferred_nfs
from .quadlet import strip_yaml_text
from .resolve import LOOPBACK, bind, render
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
        self.assertEqual(render("${secrets.immich.database_password}", m), "immich_database_password")
        self.assertNotIn("x", render("${secrets.pihole.web_password}", m))
        compute = bind(self.desired, self.desired["site"]["hosts"][1])
        self.assertEqual(compute["host.resources.gpu.gpu0"], "nvidia.com/gpu=all")
        self.assertEqual(compute["host.resources.gpu.gpu0.visible"], "all")
        self.assertEqual(
            render(
                "${host.resources.gpu.gpu0.resource}: ${host.resources.gpu.gpu0.count}",
                compute,
            ),
            "nvidia.com/gpu: 1",
        )
        hidden = bind(self.desired, {**self.desired["site"]["hosts"][1], "resources": {"gpu": [{"id": "gpu0", "visible": False}]}})
        self.assertEqual(hidden["host.resources.gpu.gpu0.visible"], "void")
        storage = bind(self.desired, self.desired["site"]["hosts"][0])
        self.assertEqual(storage["host.resources.gpu.gpu0.visible"], "all")

    def test_caddy_and_homepage(self) -> None:
        caddy = generate_caddyfile(self.desired)
        self.assertIn("auth.example.lan", caddy)
        self.assertIn("cloud.example.lan", caddy)
        home = generate_homepage_services(self.desired)
        self.assertIn(LOOPBACK, home)
        self.assertIn("HOMEPAGE_VAR_PIHOLE_TOKEN", home)

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
        # Implicit Glances on compute consumes appdata from storage; people roots stay local.
        self.assertEqual({e["path"] for e in nfs["exports"]}, {"/appdata"})
        self.assertNotIn("/users", {e["path"] for e in nfs["exports"]})
        d = load_desired(EXAMPLE)
        d["site"]["hosts"][1]["roles"]["workload"]["services"]["immich"] = None
        nfs = inferred_nfs(d)
        paths = {e["path"] for e in nfs["exports"]}
        self.assertIn("/users", paths)
        self.assertTrue(all(e["client_ip"] == "10.0.0.11" for e in nfs["exports"]))

    def test_no_service_dir_without_qbit(self) -> None:
        plan = build_plan(self.desired)
        self.assertFalse(any(d["path"].endswith("/downloads") for d in plan["service_dirs"]))

    def test_inventory_uses_sysadmin(self) -> None:
        inv = inventory_dict(self.desired)
        self.assertEqual(inv["all"]["hosts"]["storage"]["ansible_user"], "admin")
        self.assertIn("storage", inv["all"]["children"]["storage"]["hosts"])

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


if __name__ == "__main__":
    unittest.main()
