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
    "vault_ninja_admin_password",
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

    def test_gitignore_ignores_inventory_local_vault_local(self):
        content = _read(".gitignore")
        self.assertIn("ansible/inventories/*/group_vars/*/vault.local.yml", content,
                      "local plaintext vault override files under inventory group_vars must be ignored")

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
        # Pattern 'ansible/inventories/*/group_vars/*/vault.yml' must not appear.
        pattern = r"ansible/inventories/\*/group_vars/\*/vault\.yml"
        self.assertFalse(re.search(pattern, content),
                         "ansible/inventories/*/group_vars/*/vault.yml must NOT be ignored")

    def test_vault_yml_encrypted_prefix(self):
        if not _exists("ansible/inventories/local_vm/group_vars/local_vm/vault.yml"):
            self.skipTest("local_vm vault.yml does not exist yet (expected before Phase 1)")
        content = _read("ansible/inventories/local_vm/group_vars/local_vm/vault.yml")
        self.assertTrue(content.startswith("$ANSIBLE_VAULT;"),
                        "vault.yml must start with $ANSIBLE_VAULT;")

    def test_vault_example_no_live_stripe_keys(self):
        """vault.example.yml must not contain sk_live_ or pk_live_ keys."""
        for env in ("local_vm", "production"):
            path = f"ansible/inventories/{env}/group_vars/{env}/vault.example.yml"
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

    def test_local_vars_exists_inventory_path(self):
        self.assertTrue(
            _exists("ansible/inventories/local_vm/group_vars/local_vm/vars.yml"),
            "local_vm vars.yml must exist under inventory group_vars dir")

    def test_production_vars_exists_inventory_path(self):
        self.assertTrue(
            _exists("ansible/inventories/production/group_vars/production/vars.yml"),
            "production vars.yml must exist under inventory group_vars dir")

    def test_local_vars_contains_all_required_keys(self):
        content = _read("ansible/inventories/local_vm/group_vars/local_vm/vars.yml")
        for key in REQUIRED_VARS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_production_vars_contains_all_required_keys(self):
        content = _read("ansible/inventories/production/group_vars/production/vars.yml")
        for key in REQUIRED_VARS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_local_vault_example_contains_all_required_keys(self):
        content = _read("ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, content)

    def test_production_vault_example_contains_all_required_keys(self):
        content = _read("ansible/inventories/production/group_vars/production/vault.example.yml")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, content)


# ---------------------------------------------------------------------------
# 3b. Old repo-level group_vars must be absent (Ansible won't load them)
# ---------------------------------------------------------------------------
# Ansible resolves group_vars relative to the inventory file directory.
# With `inventory = inventories/local_vm/hosts.yml` in ansible.cfg,
# Ansible loads group_vars from:
#   inventories/local_vm/group_vars/<group_name>/vars.yml
# NOT from an arbitrary repo-level ansible/group_vars directory.
# Old files at ansible/group_vars/... must not exist to prevent confusion
# and accidental re-introduction.


class TestNoRepoLevelGroupVars(unittest.TestCase):
    """Verify old repo-level group_vars paths are absent."""

    def test_no_local_vm_repo_vars(self):
        self.assertFalse(
            _exists("ansible/group_vars/local_vm/vars.yml"),
            "ansible/group_vars/local_vm/vars.yml must NOT exist; "
            "vars must live under inventories/local_vm/group_vars/local_vm/")

    def test_no_production_repo_vars(self):
        self.assertFalse(
            _exists("ansible/group_vars/production/vars.yml"),
            "ansible/group_vars/production/vars.yml must NOT exist; "
            "vars must live under inventories/production/group_vars/production/")

    def test_no_local_vm_repo_vault_example(self):
        self.assertFalse(
            _exists("ansible/group_vars/local_vm/vault.example.yml"),
            "ansible/group_vars/local_vm/vault.example.yml must NOT exist; "
            "vault.example must live under inventories/local_vm/group_vars/local_vm/")

    def test_no_production_repo_vault_example(self):
        self.assertFalse(
            _exists("ansible/group_vars/production/vault.example.yml"),
            "ansible/group_vars/production/vault.example.yml must NOT exist; "
            "vault.example must live under inventories/production/group_vars/production/")


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
# 5. Templates — role-local templates (Ansible lookup path contract)
# ---------------------------------------------------------------------------
# Ansible role template/action modules resolve relative to the role
# directory.  A task inside `ansible/roles/<role>/tasks/main.yml` that uses
# `src: some_file.j2` will be searched for in:
#
#   ansible/roles/<role>/templates/some_file.j2
#
# Templates MUST live inside their owning role's templates directory.
# Shared top-level `ansible/templates/*.j2` must NOT exist (Section 5e).


class TestTemplates(unittest.TestCase):
    """Section 5 of requirements: Compose, env, Caddyfile, backup templates.

    All templates are looked up from their owning role's `templates/`
    directory to match Ansible's role-local template lookup semantics.
    """

    # -- docker-compose.yml.j2 (football_club_stack role) --

    def test_compose_template_exists(self):
        self.assertTrue(
            _exists("ansible/roles/football_club_stack/templates/docker-compose.yml.j2"),
            "docker-compose.yml.j2 must be inside the owning role's templates dir")

    def test_compose_template_is_role_local(self):
        """Template must be under ansible/roles/<role>/templates/, not in shared ansible/templates/."""
        self.assertFalse(
            _exists("ansible/templates/docker-compose.yml.j2"),
            "docker-compose.yml.j2 must NOT exist in shared ansible/templates/; "
            "it belongs inside ansible/roles/football_club_stack/templates/")

    def test_compose_services_exist(self):
        content = _read("ansible/roles/football_club_stack/templates/docker-compose.yml.j2")
        for svc in TestTemplates._COMPOSE_SERVICES:
            with self.subTest(service=svc):
                self.assertIn(svc, content)

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

    _COMPOSE_PORTS = [
        "127.0.0.1:8081:80",
        "127.0.0.1:8082:80",
        "127.0.0.1:5678:5678",
        "127.0.0.1:3000:3000",
    ]

    def test_compose_exposes_all_host_ports(self):
        content = _read("ansible/roles/football_club_stack/templates/docker-compose.yml.j2")
        for port in self._COMPOSE_PORTS:
            with self.subTest(port=port):
                self.assertIn(port, content)

    # -- env.j2 (football_club_stack role) --

    def test_env_template_exists(self):
        self.assertTrue(
            _exists("ansible/roles/football_club_stack/templates/env.j2"),
            "env.j2 must be inside the owning role's templates dir")

    def test_env_template_is_role_local(self):
        """Template must be under ansible/roles/<role>/templates/, not in shared ansible/templates/."""
        self.assertFalse(
            _exists("ansible/templates/env.j2"),
            "env.j2 must NOT exist in shared ansible/templates/; "
            "it belongs inside ansible/roles/football_club_stack/templates/")

    def test_env_template_maps_vault_vars(self):
        """env.j2 must reference the required vault_* variables."""
        content = _read("ansible/roles/football_club_stack/templates/env.j2")
        for key in REQUIRED_VAULT_KEYS:
            with self.subTest(vault_var=key):
                self.assertIn(
                    key, content, f"env.j2 must reference vault variable: {key}")

    # -- Caddyfile.j2 (caddy role) --

    def test_caddyfile_template_exists(self):
        self.assertTrue(
            _exists("ansible/roles/caddy/templates/Caddyfile.j2"),
            "Caddyfile.j2 must be inside the owning role's templates dir")

    def test_caddyfile_template_is_role_local(self):
        """Template must be under ansible/roles/<role>/templates/, not in shared ansible/templates/."""
        self.assertFalse(
            _exists("ansible/templates/Caddyfile.j2"),
            "Caddyfile.j2 must NOT exist in shared ansible/templates/; "
            "it belongs inside ansible/roles/caddy/templates/")

    _CADDY_PORTS = [
        "127.0.0.1:8081",
        "127.0.0.1:8082",
        "127.0.0.1:5678",
        "127.0.0.1:3000",
    ]

    def test_caddyfile_proxies_all_ports(self):
        content = _read("ansible/roles/caddy/templates/Caddyfile.j2")
        for port in self._CADDY_PORTS:
            with self.subTest(port=port):
                self.assertIn(port, content)

    # -- backup.sh.j2 (backup role) --

    def test_backup_template_exists(self):
        self.assertTrue(
            _exists("ansible/roles/backup/templates/backup.sh.j2"),
            "backup.sh.j2 must be inside the owning role's templates dir")

    def test_backup_template_is_role_local(self):
        """Template must be under ansible/roles/<role>/templates/, not in shared ansible/templates/."""
        self.assertFalse(
            _exists("ansible/templates/backup.sh.j2"),
            "backup.sh.j2 must NOT exist in shared ansible/templates/; "
            "it belongs inside ansible/roles/backup/templates/")

    _BACKUP_CONTENT = [
        "dolibarr",   # dolibarr DB dump
        "ninja",      # InvoiceNinja DB dump
        "n8n",        # n8n DB dump
        "tar czf",    # volume archive (tar.gz)
        "rsync",      # remote sync
        "mtime +30",  # retention cleanup (>30 days)
    ]

    def test_backup_script_includes_all_sections(self):
        content = _read("ansible/roles/backup/templates/backup.sh.j2")
        for pattern in self._BACKUP_CONTENT:
            with self.subTest(section=pattern):
                self.assertIn(pattern, content)


# ---------------------------------------------------------------------------
# 5e. Old shared templates must be absent (regression guard)
# ---------------------------------------------------------------------------
# After moving templates into owning role `templates/` dirs, the old
# shared `ansible/templates/*.j2` directory must be removed. Leaving it
# around causes confusion and can lead to re-introducing unreachable
# templates that Ansible will never find.


class TestNoOldSharedTemplates(unittest.TestCase):
    """Verify old shared `ansible/templates/` template files are absent."""

    _OLD_TEMPLATE_FILES = [
        "ansible/templates/docker-compose.yml.j2",
        "ansible/templates/env.j2",
        "ansible/templates/Caddyfile.j2",
        "ansible/templates/backup.sh.j2",
    ]

    def test_old_templates_are_absent(self):
        """None of the old shared template paths should exist in the repo."""
        for path in self._OLD_TEMPLATE_FILES:
            with self.subTest(path=path):
                self.assertFalse(
                    _exists(path),
                    f"Old shared template '{path}' must NOT exist; "
                    f"move it to its owning role's templates directory")

    def test_old_shared_templates_dir_is_absent(self):
        """The entire `ansible/templates/` directory should be removed once empty."""
        import pathlib
        old_dir = REPO_ROOT / "ansible/templates"
        self.assertFalse(
            old_dir.exists(),
            "Shared ansible/templates/ directory must be removed after all "
            "templates are moved into owning role templates/ directories")


# ---------------------------------------------------------------------------
# 5b. Ansible callback configuration (callback bug fix)
# ---------------------------------------------------------------------------

# Modern Ansible (core >= 2.13) removed `community.general.yaml` callback.
# `stdout_callback = yaml` now silently resolves to the removed plugin and
# causes a fatal error before any play execution starts:
#
#   The 'community.general.yaml' callback plugin has been removed. ...
#
# The correct configuration is:
#   stdout_callback = default
#   callback_result_format = yaml
#
# See: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/default_callback.html


class TestAnsibleCallbackConfig(unittest.TestCase):
    """Contract tests for the Ansible stdout callback configuration.

    These tests guard against the regression where `stdout_callback = yaml`
    resolves to the removed `community.general.yaml` plugin on modern Ansible,
    causing playbook execution to fail before any task runs.
    """

    def _read_cfg(self) -> str:
        return _read("ansible/ansible.cfg")

    def test_ansible_cfg_stdout_callback_is_default(self):
        """stdout_callback must be set to 'default' so Ansible uses the
        built-in callback from ansible-core instead of the removed plugin."""
        content = self._read_cfg()
        self.assertIn("stdout_callback = default", content,
                      "ansible.cfg must contain 'stdout_callback = default'; "
                      "'stdout_callback = yaml' is removed since Ansible 2.13")

    def test_ansible_cfg_no_stdout_yaml(self):
        """stdout_callback must NOT be set to 'yaml'.

        A bare value of ``yaml`` resolves to the removed
        `community.general.yaml` plugin and causes:

            The 'community.general.yaml' callback plugin has been removed.
        """
        content = self._read_cfg()
        # Match the exact key=value pair to avoid false positives from
        # comments or other lines mentioning 'yaml'.
        pattern = re.compile(r"^\s*stdout_callback\s*=\s*yaml\s*$", re.MULTILINE)
        self.assertFalse(pattern.search(content),
                         "ansible.cfg must not contain 'stdout_callback = yaml'; "
                         "this value was removed in Ansible 2.13 and causes a fatal error")

    def test_ansible_cfg_callback_result_format_yaml(self):
        """callback_result_format must be set to 'yaml' under [defaults]
        so the default callback outputs YAML-formatted results."""
        content = self._read_cfg()
        self.assertIn("callback_result_format = yaml", content,
                      "ansible.cfg must contain 'callback_result_format = yaml'; "
                      "this option replaces the old result_format setting in "
                      "the ansible.builtin.default callback")


# ---------------------------------------------------------------------------
# 5c. Inventory group hierarchy (group_vars loading bug fix)
# ---------------------------------------------------------------------------
# During Task 9 local VM dry-run the common role failed with:
#
#   football_club_project_dir is undefined
#
# Root cause: the inventory only defined `football_club` as a direct child of
# `all`, so Ansible never loaded `group_vars/local_vm/vars.yml`. The same bug
# existed for production with no `production:` group parent.
#
# Proper structure requires an environment-level group that wraps
# `football_club` so Ansible's group_vars resolution picks up the correct
# variable files per environment:
#
#   local_vm/hosts.yml :
#     all:
#       children:
#         local_vm:              <-- environment wrapper group
#           children:
#             football_club:      <-- play-target group (preserved)
#               hosts:
#                 local-vm: ...  <-- host entry (preserved)
#
#   production/hosts.yml:
#     all:
#       children:
#         production:            <-- environment wrapper group
#           children:
#             football_club:      <-- play-target group (preserved)
#               hosts:
#                 production: ... <-- host entry (preserved)
#
# The environment group must appear BEFORE football_club in the YAML so that
# the hierarchy is correct.


class TestInventoryGroupHierarchy(unittest.TestCase):
    """Contract tests for inventory group hierarchy that enables group_vars loading.

    These tests verify that each inventory defines an environment-level parent
    group (`local_vm:` or `production:`) wrapping `football_club:`, ensuring
    Ansible loads the correct group_vars directory during playbook execution.
    """

    # -- local_vm inventory --

    def test_local_inventory_has_local_vm_group(self):
        """Inventory must define a `local_vm:` top-level environment group."""
        content = _read("ansible/inventories/local_vm/hosts.yml")
        self.assertIn("local_vm:", content,
                      "local_vm inventory must contain 'local_vm:' group; "
                      "without it, group_vars/local_vm/vars.yml is not loaded")

    def test_local_inventory_still_has_football_club_group(self):
        """Inventory must still define `football_club:` as play-target group."""
        content = _read("ansible/inventories/local_vm/hosts.yml")
        self.assertIn("football_club", content,
                      "local_vm inventory must contain 'football_club' group")

    def test_local_inventory_still_has_local_vm_host(self):
        """Inventory must still define `local-vm:` as the host entry."""
        content = _read("ansible/inventories/local_vm/hosts.yml")
        self.assertIn("local-vm:", content,
                      "local_vm inventory must contain 'local-vm:' host entry")

    def test_local_inventory_environment_group_wraps_football_club(self):
        """`local_vm:` must appear before `football_club:` in YAML,
        confirming the environment group wraps the play-target group."""
        content = _read("ansible/inventories/local_vm/hosts.yml")
        local_vm_pos = content.find("local_vm:")
        football_club_pos = content.find("football_club")
        self.assertGreater(local_vm_pos, 0,
                           "'local_vm:' must be present in inventory")
        self.assertGreater(football_club_pos, 0,
                           "'football_club' must be present in inventory")
        self.assertLess(local_vm_pos, football_club_pos,
                        "'local_vm:' must appear before 'football_club' to "
                        "establish environment-wrapper hierarchy for group_vars loading")

    # -- production inventory --

    def test_production_inventory_has_production_group(self):
        """Inventory must define a `production:` top-level environment group."""
        content = _read("ansible/inventories/production/hosts.yml")
        self.assertIn("production:", content,
                      "production inventory must contain 'production:' group; "
                      "without it, group_vars/production/vars.yml is not loaded")

    def test_production_inventory_still_has_football_club_group(self):
        """Inventory must still define `football_club:` as play-target group."""
        content = _read("ansible/inventories/production/hosts.yml")
        self.assertIn("football_club", content,
                      "production inventory must contain 'football_club' group")

    def test_production_inventory_still_has_production_host(self):
        """Inventory must still define `production:` as the host entry."""
        content = _read("ansible/inventories/production/hosts.yml")
        self.assertIn("production:", content,
                      "production inventory must contain 'production:' host entry")

    def test_production_inventory_environment_group_wraps_football_club(self):
        """`production:` must appear before `football_club:` in YAML,
        confirming the environment group wraps the play-target group."""
        content = _read("ansible/inventories/production/hosts.yml")
        production_pos = content.find("production:")
        football_club_pos = content.find("football_club")
        self.assertGreater(production_pos, 0,
                           "'production:' must be present in inventory")
        self.assertGreater(football_club_pos, 0,
                           "'football_club' must be present in inventory")
        self.assertLess(production_pos, football_club_pos,
                        "'production:' must appear before 'football_club' to "
                        "establish environment-wrapper hierarchy for group_vars loading")


# ---------------------------------------------------------------------------
# 5d. yamllint ignores encrypted vault files
# ---------------------------------------------------------------------------
# Encrypted Ansible Vault files start with `$ANSIBLE_VAULT;` which is NOT valid
# YAML and will trigger `missing document start '---'` from yamllint.
# Committed encrypted vault.yml files must be excluded from yamllint scans,
# while vault.example.yml (plaintext template) MUST remain linted.
#
# See: https://yamllint.readthedocs.io/en/stable/configuration.html#ignoring-paths


class TestYamllintIgnoresEncryptedVault(unittest.TestCase):
    """Contract test: .yamllint.yml must ignore encrypted vault files.

    Encrypted Ansible Vault files (matching the committed path pattern for
    `vault.yml` under inventory group_vars) start with `$ANSIBLE_VAULT;`
    which is not valid YAML. yamllint will emit:

        missing document start "---"

    on every line. These files must be excluded via an `ignore:` block in
    `.yamllint.yml` so that linting only runs on real YAML files.

    `vault.example.yml` (plaintext template) MUST NOT be ignored and must
    continue to be linted as normal YAML.
    """

    def test_yamllint_ignore_section_exists(self):
        """`.yamllint.yml` must contain an `ignore:` section."""
        content = _read(".yamllint.yml")
        self.assertIn("ignore:", content,
                      ".yamllint.yml must have an 'ignore:' section to exclude "
                      "encrypted vault files from yamllint")

    def test_yamllint_ignores_encrypted_vault_path(self):
        """`.yamllint.yml` must ignore `**/vault.yml` (encrypted vault files).

        This glob pattern matches all committed encrypted vault files under
        inventory group_vars directories, e.g.:
          - ansible/inventories/local_vm/group_vars/local_vm/vault.yml
          - ansible/inventories/production/group_vars/production/vault.yml
        """
        content = _read(".yamllint.yml")
        self.assertIn("**/vault.yml", content,
                      ".yamllint.yml must ignore '**/vault.yml' to exclude "
                      "encrypted Ansible Vault files from yamllint scanning; "
                      "without this, yamllint emits 'missing document start ---' "
                      "warnings on every encrypted file line")

    def test_yamllint_does_not_ignore_vault_example(self):
        """`.yamllint.yml` must NOT ignore `vault.example.yml`.

        Plaintext example files are YAML templates and should remain subject
        to yamllint checks.
        """
        content = _read(".yamllint.yml")
        self.assertNotIn("vault.example", content,
                         ".yamllint.yml must NOT ignore 'vault.example.yml'; "
                         "plaintext example files should still be linted")

    def test_yamllint_ignore_is_block_scalar(self):
        """The `ignore:` value in `.yamllint.yml` must be a block scalar.

        yamllint parses path exclusions from an `ignore: |` block whose
        indented lines contain glob patterns.
        """
        content = _read(".yamllint.yml")
        lines = content.splitlines()
        found_ignore_block = False
        for i, line in enumerate(lines):
            if re.match(r"^ignore:\s*\|\s*$", line):
                found_ignore_block = True
                # The next non-empty line should start a list item.
                for j in range(i + 1, len(lines)):
                    if not lines[j].strip():
                        continue
                    self.assertTrue(lines[j].startswith("  "),
                                    f"Expected indented glob under 'ignore: |' "
                                    f"but found: '{lines[j]}'")
                    break
        self.assertTrue(found_ignore_block,
                        "'ignore: |' block must be present in .yamllint.yml")


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
# 7. InvoiceNinja runtime environment contract (missing APP_ENV fix)
# ---------------------------------------------------------------------------
# Runtime logs show:
#
#   invoiceninja-1 | /usr/local/bin/init.sh: 55: APP_ENV: parameter not set
#
# The `invoiceninja` service env block in docker-compose.yml.j2 currently
# defines APP_URL, APP_KEY, DB_*, and NINJA_LICENSE but lacks the four
# required runtime environment variables that InvoiceNinja expects inside
# Docker:
#
#   - APP_ENV: production
#   - APP_DEBUG: "false"
#   - REQUIRE_HTTPS: "true"
#   - IS_DOCKER: "true"
#
# Without these the container fails to start.


class TestInvoiceNinjaEnvVars(unittest.TestCase):
    """Contract tests: InvoiceNinja service must declare required runtime env vars.

    Each test extracts the invoiceninja service block from the Jinja2 template
    and asserts that a specific environment variable key-value pair is present.
    Uses only stdlib (re, pathlib).
    """

    _SERVICE_KEY = "invoiceninja"
    _NEEDED_VARS = [
        ("APP_ENV", "production"),
        ("APP_DEBUG", '"false"'),
        ("REQUIRE_HTTPS", '"true"'),
        ("IS_DOCKER", '"true"'),
    ]
    _BOOTSTRAP_USER_VARS = [
        ("IN_USER_EMAIL", "${ADMIN_EMAIL}"),
        ("IN_PASSWORD", "${NINJA_ADMIN_PASSWORD}"),
        ("IN_USER", "Admin"),
    ]

    def _extract_service_block(self) -> str:
        """Return the text between the invoiceninja service key and the next top-level key."""
        content = _read(
            "ansible/roles/football_club_stack/templates/docker-compose.yml.j2"
        )
        # Find start of the invoiceninja service block.
        start_match = re.search(
            r"^\s+invoiceninja:", content, re.MULTILINE
        )
        if not start_match:
            self.fail("Could not find 'invoiceninja:' service in docker-compose.yml.j2")
        # Find the end: next line at column 0 that is non-empty and not a volume/service indent.
        after_start = content[start_match.end():]
        end_match = re.search(r"^\S", after_start, re.MULTILINE)
        if end_match:
            return after_start[:end_match.start()]
        # If no other top-level key follows, return the rest.
        return after_start

    def _assert_env_var_present(self, var_name: str, var_value: str) -> None:
        """Assert that `var_name: <value>` exists inside the invoiceninja env block."""
        block = self._extract_service_block()
        # Value may or may not be quoted in YAML (e.g. production vs "false").
        escaped_value = re.escape(var_value)
        sq = chr(39)  # single-quote char
        dq = chr(34)  # double-quote char
        q = "[" + sq + dq + "]?"  # optional quote character
        pat = (r"^\s+" + re.escape(var_name) + r":\s*" + q
               + escaped_value + q + r"\s*$")
        self.assertTrue(
            re.search(pat, block, re.MULTILINE),
            "invoiceninja environment must contain {name}: {value}".format(
                name=var_name, value=var_value
            ),
        )

    def test_invoiceninja_service_exists(self):
        """The docker-compose template must define an invoiceninja service."""
        content = _read(
            "ansible/roles/football_club_stack/templates/docker-compose.yml.j2"
        )
        self.assertIn(
            "invoiceninja:", content,
            "docker-compose.yml.j2 must define an 'invoiceninja:' service"
        )

    def test_invoiceninja_env_app_env(self):
        """invoiceninja environment must contain APP_ENV: production.

        Without this the init.sh script crashes with:
          /usr/local/bin/init.sh: 55: APP_ENV: parameter not set
        """
        self._assert_env_var_present("APP_ENV", "production")

    def test_invoiceninja_env_app_debug(self):
        """invoiceninja environment must contain APP_DEBUG: \"false\".

        Production deployments should never run with debug mode on.
        """
        self._assert_env_var_present("APP_DEBUG", '"false"')

    def test_invoiceninja_env_require_https(self):
        """invoiceninja environment must contain REQUIRE_HTTPS: \"true\".

        All traffic to InvoiceNinja goes through Caddy (TLS) so the app
        must enforce HTTPS.
        """
        self._assert_env_var_present("REQUIRE_HTTPS", '"true"')

    def test_invoiceninja_env_is_docker(self):
        """invoiceninja environment must contain IS_DOCKER: \"true\".

        InvoiceNinja's Docker entrypoint uses this flag to apply Docker-
        specific configuration. Without it the container starts in a
        non-Docker mode and may misbehave.
        """
        self._assert_env_var_present("IS_DOCKER", '"true"')

    def test_invoiceninja_all_required_env_vars_present(self):
        """All four required InvoiceNinja env vars must be declared together."""
        block = self._extract_service_block()
        for var_name, var_value in self._NEEDED_VARS:
            with self.subTest(var=var_name, val=var_value):
                self._assert_env_var_present(var_name, var_value)

    # ---------------------------------------------------------------------------
    # Bootstrap user environment variables (IN_USER_EMAIL, IN_PASSWORD, IN_USER)
    # ---------------------------------------------------------------------------
    # Runtime logs show:
    #
    #   invoiceninja-1 | /usr/local/bin/init.sh: 67: IN_USER_EMAIL: parameter not set
    #
    # The `invoiceninja` service env block is missing the three bootstrap user
    # variables that InvoiceNinja's init.sh expects on first startup:
    #
    #   - IN_USER_EMAIL: ${ADMIN_EMAIL}
    #   - IN_PASSWORD: ${NINJA_ADMIN_PASSWORD}
    #   - IN_USER: Admin
    #
    # Without these the container crashes before creating the admin user.

    def test_invoiceninja_bootstrap_user_email(self):
        """invoiceninja environment must contain IN_USER_EMAIL: ${ADMIN_EMAIL}.

        Without this the init.sh script crashes with:
          /usr/local/bin/init.sh: 67: IN_USER_EMAIL: parameter not set
        """
        self._assert_env_var_present("IN_USER_EMAIL", "${ADMIN_EMAIL}")

    def test_invoiceninja_bootstrap_user_password(self):
        """invoiceninja environment must contain IN_PASSWORD: ${NINJA_ADMIN_PASSWORD}.

        Without this the init.sh script cannot set the admin user password:
          /usr/local/bin/init.sh: 67: IN_PASSWORD: parameter not set
        """
        self._assert_env_var_present("IN_PASSWORD", "${NINJA_ADMIN_PASSWORD}")

    def test_invoiceninja_bootstrap_user_name(self):
        """invoiceninja environment must contain IN_USER: Admin.

        InvoiceNinja's init.sh uses this as the admin username. Without it
        the bootstrap user creation fails.
        """
        self._assert_env_var_present("IN_USER", "Admin")

    def test_invoiceninja_bootstrap_user_vars_all_present(self):
        """All three InvoiceNinja bootstrap user env vars must be declared."""
        block = self._extract_service_block()
        for var_name, var_value in self._BOOTSTRAP_USER_VARS:
            with self.subTest(var=var_name, val=var_value):
                self._assert_env_var_present(var_name, var_value)


# ---------------------------------------------------------------------------
# 5g. InvoiceNinja volume ownership
# ---------------------------------------------------------------------------

class TestInvoiceNinjaVolumeOwnership(unittest.TestCase):
    """InvoiceNinja runs as uid/gid 999 and needs writable named volumes.

    Local VM evidence showed the container runs as uid/gid 999 and uses `/app`
    as the Laravel runtime directory. The stack role must mount and prepare only
    the InvoiceNinja app volumes before `docker compose up` starts the service.
    """

    def _tasks(self) -> str:
        return _read("ansible/roles/football_club_stack/tasks/main.yml")

    def _compose_template(self) -> str:
        return _read("ansible/roles/football_club_stack/templates/docker-compose.yml.j2")

    def test_invoiceninja_volumes_mount_to_app_runtime_paths(self):
        """InvoiceNinja Octane uses /app as the Laravel runtime directory."""
        content = self._compose_template()
        self.assertIn("ninja_storage:/app/storage", content)
        self.assertNotIn("ninja_public:/app/public", content)
        self.assertNotIn("/app/public", content,
                         "Do not mount /app/public; it contains image-built assets")
        self.assertNotIn("ninja_storage:/var/app/storage", content)
        self.assertNotIn("ninja_public:/var/app/public", content)

    def test_invoiceninja_public_volume_is_not_defined(self):
        """A public volume masks InvoiceNinja's built Vite assets."""
        content = self._compose_template()
        self.assertNotIn("ninja_public:", content)

    def test_invoiceninja_named_volumes_are_created_before_stack_start(self):
        content = self._tasks()
        self.assertIn("docker volume create", content)
        self.assertNotIn("community.docker.docker_volume", content,
                         "Volume creation must not require Docker SDK on target")
        self.assertIn("{{ football_club_compose_project_name }}_ninja_storage", content)
        self.assertNotIn("{{ football_club_compose_project_name }}_ninja_public", content)

    def test_invoiceninja_storage_subdirectories_are_created(self):
        content = self._tasks()
        for path in (
            "/mnt/ninja-volume/framework/cache/data",
            "/mnt/ninja-volume/framework/sessions",
            "/mnt/ninja-volume/framework/views",
            "/mnt/ninja-volume/logs",
        ):
            with self.subTest(path=path):
                self.assertIn(path, content)

    def test_invoiceninja_named_volumes_are_chowned_to_ninja_user(self):
        content = self._tasks()
        self.assertIn("chown -R 999:999", content,
                      "InvoiceNinja volumes must be owned by uid/gid 999")
        self.assertIn("/mnt/ninja-volume", content,
                      "Ownership helper must mount each named volume before chown")

    def test_invoiceninja_volume_preparation_runs_before_compose_up(self):
        content = self._tasks()
        prepare_pos = content.find("Prepare InvoiceNinja Docker volumes")
        start_pos = content.find("Start football club stack")
        self.assertGreaterEqual(prepare_pos, 0,
                                "Stack role must prepare InvoiceNinja volumes")
        self.assertGreaterEqual(start_pos, 0,
                                "Stack role must still start the Compose stack")
        self.assertLess(prepare_pos, start_pos,
                        "InvoiceNinja volume ownership must be fixed before compose up")

    def test_volume_ownership_fix_is_not_applied_to_database_volumes(self):
        content = self._tasks()
        self.assertNotIn("dolibarr_db_data", content)
        self.assertNotIn("ninja_db_data", content)
        self.assertNotIn("n8n_db_data", content)


# ---------------------------------------------------------------------------
# 5h. Docuseal DATABASE_URL / WORKDIR runtime contract
# ---------------------------------------------------------------------------
# VM runtime evidence for docuseal/docuseal:latest shows that the container
# uses a Ruby heredoc in /app/config/database.yml which only matches SQLite
# when DATABASE_URL is empty (nil). It also respects the `WORKDIR` env var
# as the SQLite database directory.
#
# If `DATABASE_URL=sqlite3:///data/docuseal.sqlite3` is set, none of the
# heredoc branches match, Rails produces an empty production configuration,
# and Docuseal crashes with:
#
#   ActiveRecord::DatabaseConfigurations::InvalidConfigurationError:
#     '{ production => }' is not a valid configuration.
#
# A VM hotfix that removed DATABASE_URL and set WORKDIR=/data made Puma boot
# successfully. The Compose template and all docs snippets prescribing the
# stack must encode this fix so it does not re-introduce the bug.


def _extract_docuseal_compose_block(content: str) -> str:
    """Find the ``  docuseal:`` service line in YAML content and return the
    block up to the next top-level key (line starting at column 0 ending with
    ``:``) or a closing fenced-code-block fence (```).

    Works for both docker-compose.yml.j2 (pure YAML) and markdown files that
    embed a Compose block inside triple-backtick fences. Uses regex so it
    finds ``  docuseal:`` anywhere in the text, then slices forward.
    """
    start_match = re.search(r"^\s{2}docuseal:", content, re.MULTILINE)
    if not start_match:
        return ""
    after_start = content[start_match.end():]
    # A Compose block ends at the next line starting at column 0.  We stop
    # on either a closing fence or a top-level YAML key (word followed by ``:``).
    for m in re.finditer(
        r"^(`{3,}|[a-zA-Z_]\w*:\s*$)", after_start, re.MULTILINE
    ):
        return after_start[: m.start()]
    return after_start


def _extract_docuseal_block_from_yaml(content: str) -> str:
    """Like _extract_docuseal_compose_block but for ansible templates where
    docuseal is indented 2 spaces (the same pattern).
    """
    return _extract_docuseal_compose_block(content)


class TestDocusealDatabaseContract(unittest.TestCase):
    """Contract tests: Docuseal service must NOT set DATABASE_URL for SQLite
    and MUST set WORKDIR=/data in its environment.

    These tests verify the runtime contract that prevents the
    ActiveRecord::InvalidConfigurationError crash described above.
    Uses only stdlib (re, pathlib).
    """

    _COMPOSE_TEMPLATE = (
        "ansible/roles/football_club_stack/templates/docker-compose.yml.j2"
    )

    def _compose_content(self) -> str:
        return _read(self._COMPOSE_TEMPLATE)

    def _extract_docuseal_block(self) -> str:
        """Return the docuseal service block from the compose template."""
        content = self._compose_content()
        block = _extract_docuseal_compose_block(content)
        if not block:
            self.fail("Could not find 'docuseal:' service in docker-compose.yml.j2")
        return block

    # -- Template tests --

    def test_docuseal_no_sqlite_database_url_in_compose(self):
        """docuseal service must NOT contain DATABASE_URL for SQLite.

        Setting `DATABASE_URL: sqlite3:///data/docuseal.sqlite3` causes
        Docuseal's database.yml to produce an empty Rails configuration,
        which crashes the container on boot with:

          ActiveRecord::DatabaseConfigurations::InvalidConfigurationError:
            '{ production => }' is not a valid configuration.
        """
        content = self._compose_content()
        self.assertNotIn(
            "DATABASE_URL: sqlite3:///data/docuseal.sqlite3",
            content,
            "docuseal service must NOT contain DATABASE_URL for SQLite; "
            "this env var breaks Docuseal's database.yml and crashes Puma on boot. "
            "Remove it and use WORKDIR=/data instead.",
        )

    def test_docuseal_no_any_sqlite_database_url(self):
        """docuseal environment must NOT contain any DATABASE_URL line referencing SQLite."""
        block = self._extract_docuseal_block()
        pat = re.compile(r"DATABASE_URL\s*:\s*sqlite3://", re.IGNORECASE)
        self.assertFalse(
            pat.search(block),
            "docuseal environment must not contain any DATABASE_URL set to a sqlite3:// URL; "
            "this breaks Docuseal's Rails configuration. Remove it and use WORKDIR=/data instead.",
        )

    def test_docuseal_workdir_data_in_compose(self):
        """docuseal environment must contain WORKDIR: /data.

        The docuseal/docuseal:latest container uses WORKDIR as the SQLite
        database directory. Without this, the database file is written to
        /app (container default) and may be lost or inaccessible.
        """
        block = self._extract_docuseal_block()
        escaped_val = re.escape("/data")
        pat = (
            r"^\s+WORKDIR:\s*(?:\"|\')?" + escaped_val
            + r"(?:\"|\')?\s*$"
        )
        self.assertTrue(
            re.search(pat, block, re.MULTILINE),
            "docuseal environment must contain WORKDIR: /data; "
            "the container uses this as the SQLite database directory.",
        )

    # -- docs/implementation-plan.md snippet tests --

    def test_impl_plan_no_sqlite_database_url(self):
        """docs/implementation-plan.md docuseal block must NOT contain any sqlite3 DATABASE_URL."""
        content = _read("docs/implementation-plan.md")
        block = _extract_docuseal_compose_block(content)
        self.assertTrue(
            len(block) > 0,
            "Could not find 'docuseal:' service block in docs/implementation-plan.md",
        )
        pat = re.compile(r"DATABASE_URL\s*:\s*sqlite3://", re.IGNORECASE)
        self.assertFalse(
            pat.search(block),
            "docs/implementation-plan.md docuseal block must NOT contain DATABASE_URL with sqlite3://; "
            "this crashes Docuseal on boot.",
        )

    def test_impl_plan_prescribes_workdir_data(self):
        """docs/implementation-plan.md must prescribe WORKDIR: /data for Docuseal."""
        content = _read("docs/implementation-plan.md")
        block = _extract_docuseal_compose_block(content)
        self.assertTrue(
            len(block) > 0,
            "Could not find 'docuseal:' service block in docs/implementation-plan.md",
        )
        self.assertIn(
            "WORKDIR: /data",
            block,
            "docs/implementation-plan.md must prescribe WORKDIR: /data "
            "for the Docuseal service.",
        )

    # -- 2026-04-26 deployment foundation plan docs tests --

    def test_foundation_plan_no_sqlite_database_url(self):
        """Foundation plan docuseal block must NOT contain any sqlite3 DATABASE_URL."""
        content = _read(
            "docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md"
        )
        block = _extract_docuseal_compose_block(content)
        self.assertTrue(
            len(block) > 0,
            "Could not find 'docuseal:' service block in deployment foundation plan",
        )
        pat = re.compile(r"DATABASE_URL\s*:\s*sqlite3://", re.IGNORECASE)
        self.assertFalse(
            pat.search(block),
            "foundation plan docuseal block must NOT contain DATABASE_URL with sqlite3://; "
            "this crashes Docuseal on boot.",
        )

    def test_foundation_plan_prescribes_workdir_data(self):
        """docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md must prescribe WORKDIR: /data for Docuseal."""
        content = _read(
            "docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md"
        )
        block = _extract_docuseal_compose_block(content)
        self.assertTrue(
            len(block) > 0,
            "Could not find 'docuseal:' service block in deployment foundation plan",
        )
        self.assertIn(
            "WORKDIR: /data",
            block,
            "deployment foundation plan must prescribe WORKDIR: /data "
            "for the Docuseal service.",
        )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
