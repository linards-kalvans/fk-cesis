"""Secret-free rendered configuration contracts; never contact deployed hosts.

Requires Jinja2 and PyYAML. Docker Compose validates the model without pulling or
starting anything. Existing host-native Invoice Ninja image approvals are tested
separately in test_invoiceninja_vm_hotpatch.py.
"""

import os
import io
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "ansible/roles/football_club_stack"
JINJA = Environment(undefined=StrictUndefined)


def render_stack(inventory):
    # Deliberately read only non-secret vars, never group_vars/*/vault.yml.
    values = {}
    for path in (
        ROLE / "defaults/main.yml",
        ROOT / f"ansible/inventories/{inventory}/group_vars/{inventory}/vars.yml",
    ):
        values.update(yaml.safe_load(path.read_text()))
    for _ in range(5):
        values = {
            key: JINJA.from_string(value).render(values)
            if isinstance(value, str) else value
            for key, value in values.items()
        }
    return JINJA.from_string(
        (ROLE / "templates/docker-compose.yml.j2").read_text()
    ).render(values)


class TestDeploymentSecurity(unittest.TestCase):
    def test_proxy_smoke_rejects_mutable_nginx_or_missing_native_caddy(self):
        import proxy_smoke

        with tempfile.TemporaryDirectory() as directory:
            for extra in (["--nginx-image", "nginx:latest"],
                          ["--caddy-binary", str(Path(directory) / "missing-caddy")]):
                with self.subTest(extra=extra), \
                     patch.object(proxy_smoke, "docker") as docker_call, \
                     patch("sys.argv", ["proxy_smoke.py", "--app-image", "sha256:" + "a" * 64, *extra]), \
                     patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        proxy_smoke.main()
                    self.assertEqual(error.exception.code, 2)
                    docker_call.assert_not_called()

    def test_proxy_smoke_refuses_remote_daemons_before_container_operations(self):
        import json
        import proxy_smoke

        for context_host, docker_host in (("ssh://example.invalid", "unix:///var/run/docker.sock"),
                                          ("unix:///var/run/docker.sock", "tcp://example.invalid:2376")):
            with self.subTest(context=context_host, host=docker_host):
                context = json.dumps([{"Endpoints": {"docker": {"Host": context_host}}}])
                with patch.object(proxy_smoke, "docker", return_value=context) as docker_call, \
                     patch("sys.argv", ["proxy_smoke.py", "--app-image", "sha256:" + "a" * 64]), \
                     patch.dict(os.environ, {"DOCKER_HOST": docker_host}), \
                     patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        proxy_smoke.main()
                    self.assertEqual(error.exception.code, 2)
                    docker_call.assert_called_once_with("context", "inspect")

    def test_proxy_boundary_is_normalized_before_php(self):
        for inventory in ("production", "local_vm"):
            services = yaml.safe_load(render_stack(inventory))["services"]
            self.assertEqual(services["invoiceninja"]["environment"]["TRUSTED_PROXIES"], "127.0.0.1,::1")
            self.assertEqual(services["nginx"]["command"], ["sh", "/etc/nginx/conf.d/start-nginx.sh"])
        nginx = (ROLE / "templates/laravel.conf").read_text()
        for header in ("FORWARDED", "X_FORWARDED_FOR", "X_FORWARDED_HOST", "X_FORWARDED_PROTO",
                       "X_FORWARDED_PORT", "X_FORWARDED_PREFIX", "X_FORWARDED_SSL", "X_FORWARDED_SERVER", "X_REAL_IP"):
            self.assertIn(f'fastcgi_param HTTP_{header} "";', nginx)
        self.assertIn('"1:https" on;', nginx)
        self.assertIn('include /tmp/football-club-host-proxy.conf;', nginx)
        startup = (ROLE / "templates/start-nginx.sh").read_text()
        self.assertIn("set_real_ip_from $gateway;", startup)
        self.assertIn("real_ip_recursive off;", startup)
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        deploy = next(task for task in tasks if task["name"] == "Deploy nginx host proxy startup script")
        self.assertEqual(deploy["ansible.builtin.template"]["src"], "start-nginx.sh")

    def test_proxy_startup_rejects_missing_or_ambiguous_routes(self):
        script = ROLE / "templates/start-nginx.sh"
        subprocess.run(["sh", "-n", str(script)], check=True)
        for route in ("", "default dev eth0", "default via invalid dev eth0",
                      "default via 172.20.0.1 dev eth0\ndefault via 172.21.0.1 dev eth1"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory:
                fake_ip = Path(directory) / "ip"
                # Each invalid route must fail before writing config or invoking
                # user/group management or nginx. Only a fake ip is on PATH.
                fake_ip.write_text("#!/bin/sh\nprintf '%s\\n' \"$TEST_ROUTE\"\n")
                fake_ip.chmod(0o755)
                result = subprocess.run(["/bin/sh", str(script)], capture_output=True,
                                        env={"PATH": directory, "TEST_ROUTE": route}, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_debug_is_false_in_both_rendered_inventories(self):
        for inventory in ("production", "local_vm"):
            with self.subTest(inventory=inventory):
                env = yaml.safe_load(render_stack(inventory))["services"]["invoiceninja"]["environment"]
                self.assertEqual(env["APP_ENV"], "production")
                self.assertEqual(env["APP_DEBUG"], "false")
                self.assertEqual(env["LOG_CHANNEL"], "stack")
                self.assertEqual(env["LOG_LEVEL"], "warning")

    def test_debug_override_is_rejected_before_any_host_changes(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        gate = tasks[0]["ansible.builtin.assert"]["that"][0]
        # Evaluate the same expression Ansible uses, including YAML boolean values.
        for value in (True, "true", "TRUE", "1", "yes", "", None):
            with self.subTest(value=value):
                result = JINJA.compile_expression(gate)(
                    football_club_stack_invoiceninja_app_debug=value
                )
                self.assertFalse(result)
        for value in (False, "false", "FALSE"):
            self.assertTrue(JINJA.compile_expression(gate)(
                football_club_stack_invoiceninja_app_debug=value
            ))

    def test_no_implicit_image_refresh(self):
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        self.assertIs(defaults["football_club_stack_pull_mms_images"], False)
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        pull = next(task for task in tasks if task["name"] == "Pull MMS images")
        self.assertEqual(pull["when"], "football_club_stack_pull_mms_images | bool")
        start = next(task for task in tasks if task["name"] == "Start football club stack")
        self.assertIn("up -d --pull never", start["ansible.builtin.command"]["cmd"])
        initialize = next(task for task in tasks if task["name"] == "Initialize InvoiceNinja storage volume for ninja user")
        self.assertIn("docker run --rm --pull never", initialize["ansible.builtin.command"]["cmd"])

    def test_no_new_floating_image_exceptions(self):
        # Transitional debt, NOT approvals of immutable runtime identities. Remove
        # each exception after independently recording the host's running digest.
        exceptions = {
            "ninja-db": "mariadb:lts",
            "ninja-cache": "redis:alpine",
            "nginx": "nginx:alpine",
            "docuseal": "docuseal/docuseal:latest",
            "mms-postgres": "postgres:18-alpine",
        }
        for inventory, tag in (("production", "main"), ("local_vm", "dev")):
            expected = {**exceptions,
                        "mms-web": f"ghcr.io/linards-kalvans/fk-cesis-mms:{tag}",
                        "mms-qcluster": f"ghcr.io/linards-kalvans/fk-cesis-mms:{tag}"}
            services = yaml.safe_load(render_stack(inventory))["services"]
            floating = {
                name: service["image"] for name, service in services.items()
                if not re.fullmatch(r"(?:.+@)?sha256:[0-9a-f]{64}", service["image"])
            }
            # Newly digest-pinned services are allowed; new floating references are not.
            for name, image in floating.items():
                with self.subTest(inventory=inventory, service=name):
                    self.assertEqual(image, expected.get(name))

    def test_only_expected_service_image_repositories(self):
        expected = {
            "ninja-db": "mariadb", "ninja-cache": "redis", "nginx": "nginx",
            "docuseal": "docuseal/docuseal", "mms-postgres": "postgres",
            "mms-web": "ghcr.io/linards-kalvans/fk-cesis-mms",
            "mms-qcluster": "ghcr.io/linards-kalvans/fk-cesis-mms",
        }
        for inventory in ("production", "local_vm"):
            services = yaml.safe_load(render_stack(inventory))["services"]
            self.assertEqual(set(services), {"invoiceninja", *expected})
            for name, repository in expected.items():
                image = services[name]["image"].split("@", 1)[0]
                with self.subTest(inventory=inventory, service=name):
                    self.assertEqual(image.split(":", 1)[0], repository)

    def test_only_loopback_ports_and_existing_volume_contract(self):
        for inventory in ("production", "local_vm"):
            model = yaml.safe_load(render_stack(inventory))
            self.assertEqual(set(model["volumes"]), {
                "app_public", "app_storage", "redis_data", "ninja_db_data",
                "docuseal_data", "mms_pgdata", "mms_uploads", "mms_private_uploads",
            })
            self.assertNotIn("networks", model)
            self.assertEqual(model["services"]["ninja-db"]["volumes"],
                             ["ninja_db_data:/var/lib/mysql"])
            self.assertEqual(model["services"]["mms-postgres"]["volumes"],
                             ["mms_pgdata:/var/lib/postgresql"])
            self.assertEqual(model["services"]["docuseal"]["volumes"],
                             ["docuseal_data:/data"])
            self.assertEqual(model["services"]["invoiceninja"]["volumes"],
                             ["app_public:/var/www/html/public", "app_storage:/var/www/html/storage"])
            for service in model["services"].values():
                for port in service.get("ports", []):
                    self.assertTrue(port.startswith("127.0.0.1:"), port)

    def test_compose_validates_both_inventories_with_synthetic_environment(self):
        if not shutil.which("docker"):
            self.skipTest("Docker Compose is required (mandatory in CI)")
        for inventory in ("production", "local_vm"):
            with self.subTest(inventory=inventory), tempfile.TemporaryDirectory() as directory:
                rendered = render_stack(inventory)
                path = Path(directory) / "compose.yml"
                path.write_text(rendered)
                # Do not inherit credentials or auto-discover any real .env file.
                env_path = Path(directory) / ".env"
                env_path.write_text("".join(
                    f"{name}=security-test-placeholder\n"
                    for name in sorted(set(re.findall(r"\$\{(\w+)\}", rendered)))
                ))
                result = subprocess.run(
                    ["docker", "compose", "--project-name", "security-config-test",
                     "--env-file", str(env_path), "-f", str(path), "config", "--quiet"],
                    env={"PATH": os.environ["PATH"], "HOME": directory},
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
