"""Check production deployment settings without loading Vault variables."""

from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


ANSIBLE = Path(__file__).resolve().parents[1] / "ansible"
ROLE = ANSIBLE / "roles/football_club_stack"


class TestProductionDocusealURL(unittest.TestCase):
    def test_production_compose_preserves_live_settings(self):
        values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        inventory = ANSIBLE / "inventories/production/group_vars/production/vars.yml"
        values.update(yaml.safe_load(inventory.read_text()))
        jinja = Environment(undefined=StrictUndefined)
        values = {
            key: jinja.from_string(value).render(values) if isinstance(value, str) else value
            for key, value in values.items()
        }
        mms_environment = {
            "SITE_URL": "https://members.fkcesis.lv",
            "DJANGO_ALLOWED_HOSTS": "members.fkcesis.lv",
            "CSRF_TRUSTED_ORIGINS": "https://members.fkcesis.lv",
            "DOCUSEAL_API_URL": "https://agreements.fkcesis.lv/api",
            "DOCUSEAL_TEMPLATE_ALLOWED_ORIGINS": "https://agreements.fkcesis.lv/",
            "AGREEMENT_PDF_SHADOW_ENABLED": "true",
            "ANALYTICS_PROVIDER": "umami",
            "ANALYTICS_BROWSER_ENABLED": "true",
            "ANALYTICS_SERVER_ENABLED": "true",
            "ANALYTICS_API_URL": "https://analytics.mplytics.eu",
            "ANALYTICS_SITE_ID": "bbe32ff3-12e7-47fa-8c5a-c2bc6ece7c67",
            "INVOICE_NINJA_API_URL": "http://nginx/api/v1",
            "OCR_PROVIDER_MODE": "tiny_idp",
        }
        template = (ROLE / "templates/docker-compose.yml.j2").read_text()
        services = yaml.safe_load(jinja.from_string(template).render(values))["services"]
        env_lines = dict(
            line.split("=", 1) for line in (ROLE / "templates/env.j2").read_text().splitlines()
            if "=" in line
        )
        self.assertEqual(jinja.from_string(env_lines["DOMAIN"]).render(values), "fkcesis.lv")
        self.assertEqual(services["invoiceninja"]["environment"]["APP_URL"], "https://billing.fkcesis.lv")
        self.assertEqual(services["invoiceninja"]["image"],
                         "invoiceninja/invoiceninja-debian@"
                         "sha256:ac7eef4794afb978ee72f317f2af2fd34d71fe557b438f19a312dea2f0597a0a")
        self.assertEqual(services["ninja-cache"]["image"], "redis:8-alpine")
        self.assertEqual(services["nginx"]["image"], "nginx:stable-alpine")
        for service in ("mms-web", "mms-qcluster"):
            with self.subTest(service=service):
                self.assertEqual(services[service]["image"], "ghcr.io/linards-kalvans/fk-cesis-mms:main")
                for key, expected in mms_environment.items():
                    ref = services[service]["environment"][key]
                    self.assertRegex(ref, r"^\$\{MMS_\w+\}$")
                    self.assertEqual(jinja.from_string(env_lines[ref[2:-1]]).render(values), expected, key)
