"""Check the production Docuseal URL without loading Vault variables."""

from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


ANSIBLE = Path(__file__).resolve().parents[1] / "ansible"
ROLE = ANSIBLE / "roles/football_club_stack"


class TestProductionDocusealURL(unittest.TestCase):
    def test_both_mms_services_receive_the_production_api_url(self):
        values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        inventory = ANSIBLE / "inventories/production/group_vars/production/vars.yml"
        values.update(yaml.safe_load(inventory.read_text()))
        env_line = next(
            line for line in (ROLE / "templates/env.j2").read_text().splitlines()
            if line.startswith("MMS_DOCUSEAL_API_URL=")
        )
        jinja = Environment(undefined=StrictUndefined)
        values = {
            key: jinja.from_string(value).render(values) if isinstance(value, str) else value
            for key, value in values.items()
        }
        url = jinja.from_string(env_line).render(values).split("=", 1)[1]
        template = (ROLE / "templates/docker-compose.yml.j2").read_text()
        rendered = jinja.from_string(template).render(values)
        services = yaml.safe_load(rendered.replace("${MMS_DOCUSEAL_API_URL}", url))["services"]
        for service in ("mms-web", "mms-qcluster"):
            with self.subTest(service=service):
                self.assertEqual(
                    services[service]["environment"]["DOCUSEAL_API_URL"],
                    "https://agreements.fkcesis.lv/api",
                )
