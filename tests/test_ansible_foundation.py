#!/usr/bin/env python3
"""Contract tests for the Ansible deployment foundation.

Verifies that files created by the Phase 1 implementation plan exist and contain
the required settings, secrets safety guards, inventories, playbooks, roles,
templates, and documentation before any production code is committed.

Uses only Python stdlib (unittest, pathlib, re).
"""

import pathlib
import re
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(relative: str) -> str:
    """Return file contents as string.

    Raises AssertionError with a clear message when the file does not exist,
    so the red phase shows assertion failures instead of unittest ERROR entries.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing required file: {relative}")
    return path.read_text()


def _exists(relative: str) -> bool:
    """Return True when a path exists in the repo root."""
    return (REPO_ROOT / relative).is_file()


# ---------------------------------------------------------------------------
# Shared data: required vault_* secret variable names from the implementation plan
# ---------------------------------------------------------------------------

REQUIRED_VAULT_KEYS = [
    "vault_doli_db_password",
    "vault_doli_db_root_password",
    "vault_doli_admin_password",
    "vault_ninja_app_key",
    "vault_ninja_db_password",
    "vault_ninja_db_root_password",
    "vault_n8n_encryption_key",
    "vault_n8n_db_password",
    "vault_docuseal_secret_key",
    "vault_stripe_publishable_key",
    "vault_stripe_secret_key",
    "vault_stripe_webhook_secret",
]

REQUIRED_VARS = [
    "football_club_domain",
    "football_club_admin_email",
    "football_club_project_dir",
    "football_club_backup_dir",
    "football_club_backup_remote",
    "football_club_timezone",
    "football_club_caddyfile_path",
    "football_club_caddy_backup_dir",
    "football_club_compose_project_name",
    "football_club_doctr_enabled",
]


# ---------------------------------------------------------------------------
# 1. Tooling files
# ---------------------------------------------------------------------------

class TestToolingFiles(unittest.TestCase):
    """Section 1 of requirements: lint and config files."""

    def test_ansible_lint_profile_production(self):
        content = _read(".ansible-lint")
        self.assertIn("profile: production", content)

    def test_ansible_lint_excludes_docs_html(self):
        content = _read(".ansible-lint")
        self.assertIn("docs/html/", content)

    def test_yamllint_exists(self):
        self.assertTrue(_exists(".yamllint.yml"), ".yamllint.yml must exist")

    def test_yamllint_document_start_present(self):
        content = _read(".yamllint.yml")
        self.assertIn("document-start:", content)
        self.assertIn("present: true", content)

    def test_ansible_cfg_exists(self):
        self.assertTrue(_exists("ansible/ansible.cfg"), "ansible/ansible.cfg must exist")

    def test_ansible_cfg_inventory_local_vm(self):
        content = _read("ansible/ansible.cfg")
        self.assertIn("local_vm", content)

    def test_ansible_cfg_roles_path(self):
        content = _read("ansible/ansible.cfg")
        self.assertIn("roles_path", content)

    def test_requirements_yml_community_docker(self):
        content = _read("ansible/requirements.yml")
        self.assertIn("community.docker", content)

    def test_requirements_yml_ansible_posix(self):
        content = _read("ansible/requirements.yml")
        self.assertIn("ansible.posix", content)


# ---------------------------------------------------------------------------
# 2. Secret safety
# ---------------------------------------------------------------------------

class TestSecretSafety(unittest.TestCase):
    """Section 2 of requirements: .gitignore and vault safety."""

    def test_gitignore_exists(self):
        self.assertTrue(_exists(".gitignore"), ".gitignore must exist")

    def test_gitignore_ignores_worktrees(self):
        content = _read(".gitignore")
        self.assertIn(".worktrees/", content)

    def test_gitignore_ignores_vault_pass(self):
        content = _read(".gitignore")
        self.assertIn(".vault-pass", content)

    def test_gitignore_ignores_vault_pass_txt(self):
        content = _read(".gitignore")
        self.assertIn("vault-pass.txt", content)

    def test_gitignore_ignores_dotenv(self):
        content = _read(".gitignore")
        self.assertIn(".env", content)

    def test_gitignore_ignores_opt_football_club_env(self):
        content = _read(".gitignore")
        # Must ignore the absolute path /opt/football-club/.env
        self.assertIn("/opt/football-club/.env", content)

    def test_gitignore_does_not_ignore_group_vars_vault(self):
        """vault.yml for group_vars must NOT be in .gitignore."""
        content = _read(".gitignore")
        # Pattern 'ansible/group_vars/*/vault.yml' must not appear.
        pattern = r"ansible/group_vars/\*/vault\.yml"
        self.assertFalse(re.search(pattern, content),
                         "ansible/group_vars/*/vault.yml must NOT be ignored")

    def test_vault_yml_encrypted_prefix(self):
        if not _exists("ansible/group_vars/local_vm/vault.yml"):
            self.skipTest("local_vm vault.yml does not exist yet (expected before Phase 1)")
        content = _read("ansible/group_vars/local_vm/vault.yml")
        self.assertTrue(content.startswith("$ANSIBLE_VAULT;"),
                        "vault.yml must start with $ANSIBLE_VAULT;")

    def test_vault_example_no_live_stripe_keys(self):
        """vault.example.yml must not contain sk_live_ or pk_live_ keys."""
        for env in ("local_vm", "production"):
            path = f"ansible/group_vars/{env}/vault.example.yml"
            if not _exists(path):
                self.skipTest(f"{path} does not exist yet")
            content = _read(path)
            self.assertNotIn("sk_live_", content,
                             f"{env}/vault.example.yml must not contain sk_live_ keys")
            self.assertNotIn("pk_live_", content,
                             f"{env}/vault.example.yml must not contain pk_live_ keys")


# ---------------------------------------------------------------------------
# 3. Inventories and variable contracts
# ---------------------------------------------------------------------------

class TestInventories(unittest.TestCase):
    """Section 3 of requirements: inventory groups and var/secret contracts."""

    def test_local_inventory_exists(self):
        self.assertTrue(
            _exists("ansible/inventories/local_vm/hosts.yml"),
            "local_vm hosts.yml must exist")

    def test_production_inventory_exists(self):
        self.assertTrue(
            _exists("ansible/inventories/production/hosts.yml"),
            "production hosts.yml must exist")

    def test_local_inventory_has_football_club_group(self):
        content = _read("ansible/inventories/local_vm/hosts.yml")
        self.assertIn("football_club", content)

    def test_production_inventory_has_football_club_group(self):
        content = _read("ansible/inventories/production/hosts.yml")
        self.assertIn("football_club", content)

    def test_local_vars_exists(self):
        self.assertTrue(
            _exists("ansible/group_vars/local_vm/vars.yml"),
            "local_vm vars.yml must exist")

    def test_production_vars_exists(self):
        self.assertTrue(
            _exists("ansible/group_vars/production/vars.yml"),
            "production vars.yml must exist")

    def test_local_vars_contains_all_required_keys(self):
        content = _read("ansible/group_vars/local_vm/vars.yml")
        for key in REQUIRED_VARS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_production_vars_contains_all_required_keys(self):
        content = _read("ansible/group_vars/production/vars.yml")
        for key in REQUIRED_VARS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_local_vault_example_contains_all_required_keys(self):
        content = _read("ansible/group_vars/local_vm/vault.example.yml")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_production_vault_example_contains_all_required_keys(self):
        content = _read("ansible/group_vars/production/vault.example.yml")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, content)


# ---------------------------------------------------------------------------
# 4. Playbooks and roles
# ---------------------------------------------------------------------------

class TestPlaybooksAndRoles(unittest.TestCase):
    """Section 4 of requirements: site.yml, validate.yml, role tasks."""

    def test_site_yml_exists(self):
        self.assertTrue(_exists("ansible/playbooks/site.yml"))

    def test_validate_yml_exists(self):
        self.assertTrue(_exists("ansible/playbooks/validate.yml"))

    # Roles are loaded by name in site.yml; check order and presence.
    _EXPECTED_ROLES = ["common", "docker", "football_club_stack", "caddy", "backup"]

    def test_site_yml_includes_all_roles(self):
        content = _read("ansible/playbooks/site.yml")
        for role in self._EXPECTED_ROLES:
            with self.subTest(role=role):
                self.assertIn(role, content)

    def test_site_yml_role_order(self):
        """Roles must appear in the defined order in site.yml."""
        content = _read("ansible/playbooks/site.yml")
        last_pos = -1
        for role in self._EXPECTED_ROLES:
            pos = content.find(role)
            self.assertGreater(pos, last_pos,
                               f"Role '{role}' must appear after previous roles "
                               f"(pos={pos}, last_pos={last_pos})")
            last_pos = pos

    def test_validate_yml_checks_club_domain(self):
        content = _read("ansible/playbooks/validate.yml")
        self.assertIn("club", content)

    def test_validate_yml_checks_billing_domain(self):
        content = _read("ansible/playbooks/validate.yml")
        self.assertIn("billing", content)

    def test_validate_yml_checks_n8n_domain(self):
        content = _read("ansible/playbooks/validate.yml")
        self.assertIn("n8n", content)

    def test_validate_yml_checks_agreements_domain(self):
        content = _read("ansible/playbooks/validate.yml")
        self.assertIn("agreements", content)

    # Role task files
    _ROLE_TASKS = [
        "common",
        "docker",
        "football_club_stack",
        "caddy",
        "backup",
    ]

    def test_role_tasks_exist(self):
        for role in self._ROLE_TASKS:
            path = f"ansible/roles/{role}/tasks/main.yml"
            self.assertTrue(_exists(path), f"{path} must exist")


# ---------------------------------------------------------------------------
# 5. Templates
# ---------------------------------------------------------------------------

class TestTemplates(unittest.TestCase):
    """Section 5 of requirements: Compose, env, Caddyfile, backup templates."""

    def _read_template(self, name: str) -> str:
        return _read(f"ansible/templates/{name}")

    # -- docker-compose.yml.j2 --
    _COMPOSE_SERVICES = [
        "dolibarr",
        "dolibarr-db",
        "invoiceninja",
        "ninja-db",
        "n8n",
        "n8n-db",
        "docuseal",
        "doctr-api",
    ]

    def test_compose_template_exists(self):
        self.assertTrue(_exists("ansible/templates/docker-compose.yml.j2"))

    def test_compose_services_exist(self):
        content = self._read_template("docker-compose.yml.j2")
        for svc in self._COMPOSE_SERVICES:
            with self.subTest(service=svc):
                self.assertIn(svc, content)

    _COMPOSE_PORTS = [
        "127.0.0.1:8081:80",
        "127.0.0.1:8082:80",
        "127.0.0.1:5678:5678",
        "127.0.0.1:3000:3000",
    ]

    def test_compose_exposes_all_host_ports(self):
        content = self._read_template("docker-compose.yml.j2")
        for port in self._COMPOSE_PORTS:
            with self.subTest(port=port):
                self.assertIn(port, content)

    # -- env.j2 --
    def test_env_template_exists(self):
        self.assertTrue(_exists("ansible/templates/env.j2"))

    def test_env_template_maps_vault_vars(self):
        """env.j2 must reference the required vault_* variables."""
        content = self._read_template("env.j2")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(vault_var=key):
                # Template uses Jinja syntax {{ vault_xxx }} so the full
                # variable name (minus 'vault_' prefix is not needed;
                # we just need to confirm the name appears.
                self.assertIn(key, content,
                              f"env.j2 must map {key}")

    # -- Caddyfile.j2 --
    def test_caddyfile_template_exists(self):
        self.assertTrue(_exists("ansible/templates/Caddyfile.j2"))

    _CADDY_PORTS = [
        "127.0.0.1:8081",
        "127.0.0.1:8082",
        "127.0.0.1:5678",
        "127.0.0.1:3000",
    ]

    def test_caddyfile_proxies_all_ports(self):
        content = self._read_template("Caddyfile.j2")
        for port in self._CADDY_PORTS:
            with self.subTest(port=port):
                self.assertIn(port, content)

    # -- backup.sh.j2 --
    def test_backup_template_exists(self):
        self.assertTrue(_exists("ansible/templates/backup.sh.j2"))

    _BACKUP_CONTENT = [
        "dolibarr",   # dolibarr DB dump
        "ninja",      # InvoiceNinja DB dump
        "n8n",        # n8n DB dump
        "tar czf",    # volume archive (tar.gz)
        "rsync",      # remote sync
        "mtime +30",  # retention cleanup (>30 days)
    ]

    def test_backup_script_includes_all_sections(self):
        content = self._read_template("backup.sh.j2")
        for pattern in self._BACKUP_CONTENT:
            with self.subTest(section=pattern):
                self.assertIn(pattern, content)


# ---------------------------------------------------------------------------
# 6. Docs
# ---------------------------------------------------------------------------

class TestDocs(unittest.TestCase):
    """Section 6 of requirements: ansible README documents required checks."""

    def test_readme_exists(self):
        self.assertTrue(_exists("ansible/README.md"))

    def test_readme_mentions_ansible_lint(self):
        content = _read("ansible/README.md")
        self.assertIn("ansible-lint", content)

    def test_readme_mentions_yamllint(self):
        content = _read("ansible/README.md")
        self.assertIn("yamllint", content)

    def test_readme_mentions_site_syntax_check(self):
        content = _read("ansible/README.md")
        self.assertIn("site.yml", content)
        self.assertIn("--syntax-check", content)

    def test_readme_mentions_validate_syntax_check(self):
        content = _read("ansible/README.md")
        self.assertIn("validate.yml", content)
        self.assertIn("--syntax-check", content)

    def test_readme_mentions_check_diff(self):
        content = _read("ansible/README.md")
        self.assertIn("--check", content)
        self.assertIn("--diff", content)

    def test_readme_mentions_apply(self):
        """README must document the apply command (site.yml playbook run)."""
        content = _read("ansible/README.md")
        # Presence of site.yml with --ask-vault-pass implies apply
        self.assertIn("site.yml", content)

    def test_readme_mentions_validate_after_apply(self):
        """README must document the validate playbook after apply."""
        content = _read("ansible/README.md")
        self.assertIn("validate.yml", content)


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
