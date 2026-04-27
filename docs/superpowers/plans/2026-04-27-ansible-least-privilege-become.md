# Ansible Least-Privilege Become Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ansible use sudo only for tasks that require root while running Docker and validation work as the unprivileged deployment user.

**Architecture:** Disable global and play-level privilege escalation, then add task-level `become: true` to root-required operations only. Add the deployment user to the Docker group so Compose lifecycle and validation commands run without Ansible sudo, accepting that Docker group membership is root-equivalent.

**Tech Stack:** Ansible, Ansible Vault, Docker Engine, Docker Compose plugin, Caddy, Python unittest, ansible-lint, yamllint.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-04-27-ansible-least-privilege-become-design.md`
- Existing deployment design: `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`
- Existing foundation plan: `docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md`
- Project instructions: `AGENTS.md`

## File Structure

Modify these files:

- `tests/test_ansible_foundation.py`: add contract tests for least-privilege become behavior.
- `ansible/ansible.cfg`: change default privilege escalation to false.
- `ansible/playbooks/site.yml`: remove play-level privilege escalation.
- `ansible/playbooks/validate.yml`: remove play-level privilege escalation.
- `ansible/roles/common/tasks/main.yml`: mark package and root directory tasks privileged.
- `ansible/roles/docker/tasks/main.yml`: mark package/service/user membership tasks privileged and reset the SSH connection.
- `ansible/roles/football_club_stack/tasks/main.yml`: mark root-owned template tasks privileged and leave Docker commands unprivileged.
- `ansible/roles/caddy/tasks/main.yml`: mark package/root-file/service tasks privileged and leave Caddy validation unprivileged.
- `ansible/roles/caddy/handlers/main.yml`: mark Caddy reload privileged.
- `ansible/roles/backup/tasks/main.yml`: mark backup script and root cron tasks privileged.
- `AGENTS.md`: document that Ansible changes must avoid global become and use task-level sudo only.

## Task 1: Add failing least-privilege contract tests

**Files:**

- Modify: `tests/test_ansible_foundation.py`

- [ ] **Step 1: Add a test class for Ansible privilege policy**

Append this class before the suite runner block. Use only Python stdlib helpers already present in the file.

```python
class TestAnsibleLeastPrivilegeBecome(unittest.TestCase):
    """Contract tests for least-privilege Ansible sudo usage.

    The deployment user is allowed in the docker group, so Docker and Compose
    commands should run without Ansible sudo. Host-level mutations still need
    task-level become.
    """

    def test_ansible_cfg_disables_global_become(self):
        content = _read("ansible/ansible.cfg")
        self.assertIn(
            "become = False",
            content,
            "ansible.cfg must default to no privilege escalation",
        )
        self.assertNotIn(
            "become = True",
            content,
            "ansible.cfg must not enable global privilege escalation",
        )

    def test_site_playbook_has_no_play_level_become(self):
        content = _read("ansible/playbooks/site.yml")
        self.assertNotRegex(
            content,
            r"(?m)^\s{2}become:\s*true\s*$",
            "site.yml must not enable become at play level",
        )

    def test_validate_playbook_has_no_play_level_become(self):
        content = _read("ansible/playbooks/validate.yml")
        self.assertNotRegex(
            content,
            r"(?m)^\s{2}become:\s*true\s*$",
            "validate.yml must not enable become at play level",
        )

    def test_docker_role_adds_deploy_user_to_docker_group(self):
        content = _read("ansible/roles/docker/tasks/main.yml")
        self.assertIn("ansible.builtin.user:", content)
        self.assertIn('name: "{{ ansible_user }}"', content)
        self.assertIn("groups: docker", content)
        self.assertIn("append: true", content)

    def test_docker_role_resets_connection_after_group_change(self):
        content = _read("ansible/roles/docker/tasks/main.yml")
        self.assertIn("ansible.builtin.meta: reset_connection", content)

    def test_docker_compose_commands_do_not_use_task_level_become(self):
        content = _read("ansible/roles/football_club_stack/tasks/main.yml")
        for task_name in (
            "Validate rendered Docker Compose config",
            "Prepare InvoiceNinja Docker volumes",
            "Initialize InvoiceNinja storage volume for ninja user",
            "Start football club stack",
        ):
            with self.subTest(task=task_name):
                pattern = re.compile(
                    rf"- name: {re.escape(task_name)}(?P<body>.*?)(?=\n- name: |\Z)",
                    re.DOTALL,
                )
                match = pattern.search(content)
                self.assertIsNotNone(match, f"Missing task: {task_name}")
                self.assertNotIn(
                    "become: true",
                    match.group("body"),
                    f"{task_name} must run as the deployment user via docker group",
                )

    def test_validate_playbook_http_checks_do_not_use_become(self):
        content = _read("ansible/playbooks/validate.yml")
        for task_name in (
            "Check Dolibarr HTTP endpoint",
            "Check InvoiceNinja HTTP endpoint",
            "Check n8n HTTP endpoint",
            "Check Docuseal HTTP endpoint",
        ):
            with self.subTest(task=task_name):
                pattern = re.compile(
                    rf"- name: {re.escape(task_name)}(?P<body>.*?)(?=\n    - name: |\Z)",
                    re.DOTALL,
                )
                match = pattern.search(content)
                self.assertIsNotNone(match, f"Missing task: {task_name}")
                self.assertNotIn("become: true", match.group("body"))

    def test_root_mutation_task_files_use_task_level_become(self):
        required_files = [
            "ansible/roles/common/tasks/main.yml",
            "ansible/roles/docker/tasks/main.yml",
            "ansible/roles/football_club_stack/tasks/main.yml",
            "ansible/roles/caddy/tasks/main.yml",
            "ansible/roles/backup/tasks/main.yml",
            "ansible/roles/caddy/handlers/main.yml",
        ]
        for path in required_files:
            with self.subTest(path=path):
                content = _read(path)
                self.assertIn(
                    "become: true",
                    content,
                    f"{path} must declare task-level become for root-required operations",
                )

    def test_env_rendered_for_deploy_user_not_root(self):
        content = _read("ansible/roles/football_club_stack/tasks/main.yml")
        env_task_pattern = re.compile(
            r"- name: Render environment file from Ansible Vault values"
            r"(?P<body>.*?)(?=\n- name: |\Z)",
            re.DOTALL,
        )
        match = env_task_pattern.search(content)
        self.assertIsNotNone(match, "Missing .env render task")
        self.assertIn(
            'owner: "{{ ansible_user }}"',
            match.group("body"),
            ".env must be owned by ansible_user so unprivileged docker compose can read it",
        )
        self.assertIn(
            'group: "{{ ansible_user }}"',
            match.group("body"),
            ".env group must be ansible_user",
        )
```

- [ ] **Step 2: Run the contract tests and verify red phase**

Run:

```bash
python3 -m unittest tests/test_ansible_foundation.py
```

Expected: FAIL. At minimum, these failures should be caused by current global/play-level become and missing Docker group task:

- `test_ansible_cfg_disables_global_become`
- `test_site_playbook_has_no_play_level_become`
- `test_validate_playbook_has_no_play_level_become`
- `test_docker_role_adds_deploy_user_to_docker_group`
- `test_docker_role_resets_connection_after_group_change`

Do not modify Ansible implementation files until this red phase is observed.

## Task 2: Implement least-privilege become in Ansible

**Files:**

- Modify: `ansible/ansible.cfg`
- Modify: `ansible/playbooks/site.yml`
- Modify: `ansible/playbooks/validate.yml`
- Modify: `ansible/roles/common/tasks/main.yml`
- Modify: `ansible/roles/docker/tasks/main.yml`
- Modify: `ansible/roles/football_club_stack/tasks/main.yml`
- Modify: `ansible/roles/caddy/tasks/main.yml`
- Modify: `ansible/roles/caddy/handlers/main.yml`
- Modify: `ansible/roles/backup/tasks/main.yml`

- [ ] **Step 1: Disable global Ansible become**

Change `ansible/ansible.cfg` privilege section to exactly:

```ini
[privilege_escalation]
become = False
become_method = sudo
become_ask_pass = False
```

- [ ] **Step 2: Remove play-level become from playbooks**

In `ansible/playbooks/site.yml`, remove the line:

```yaml
  become: true
```

The file should contain:

```yaml
---
- name: Provision FK CĒSIS football club platform
  hosts: football_club
  gather_facts: true

  roles:
    - role: common
    - role: docker
    - role: football_club_stack
    - role: caddy
    - role: backup
```

In `ansible/playbooks/validate.yml`, remove the line:

```yaml
  become: true
```

The play header should contain:

```yaml
---
- name: Validate FK CĒSIS football club platform deployment
  hosts: football_club
  gather_facts: false
```

- [ ] **Step 3: Add task-level become in common role**

Change `ansible/roles/common/tasks/main.yml` to:

```yaml
---
- name: Ensure apt cache is up to date
  ansible.builtin.apt:
    update_cache: true
    cache_valid_time: 3600
  become: true

- name: Install baseline packages
  ansible.builtin.apt:
    name:
      - ca-certificates
      - curl
      - gnupg
      - lsb-release
      - python3
      - python3-apt
      - rsync
      - tar
    state: present
  become: true

- name: Ensure project directory exists
  ansible.builtin.file:
    path: "{{ football_club_project_dir }}"
    state: directory
    owner: root
    group: root
    mode: "0755"
  become: true

- name: Ensure backup root directory exists
  ansible.builtin.file:
    path: "{{ football_club_backup_dir }}"
    state: directory
    owner: root
    group: root
    mode: "0750"
  become: true
```

- [ ] **Step 4: Add Docker group access and task-level become in docker role**

Change `ansible/roles/docker/tasks/main.yml` to:

```yaml
---
- name: Install Docker packages from Ubuntu repositories
  ansible.builtin.apt:
    name:
      - docker.io
      - docker-compose-v2
    state: present
    update_cache: true
  become: true

- name: Ensure Docker service is enabled and running
  ansible.builtin.service:
    name: docker
    enabled: true
    state: started
  become: true

- name: Allow deployment user to run Docker without sudo
  ansible.builtin.user:
    name: "{{ ansible_user }}"
    groups: docker
    append: true
  become: true
  register: docker_deploy_user_group

- name: Reset SSH connection so docker group membership is active  # noqa: no-handler
  ansible.builtin.meta: reset_connection
  when: docker_deploy_user_group.changed
```

- [ ] **Step 5: Add task-level become only to root-owned render tasks in stack role**

In `ansible/roles/football_club_stack/tasks/main.yml`, add `become: true` only to these tasks:

```yaml
- name: Render Docker Compose project
  ...
  become: true

- name: Render environment file from Ansible Vault values
  ...
  no_log: true
  become: true
```

Do not add `become: true` to these Docker command tasks:

- `Validate rendered Docker Compose config`
- `Prepare InvoiceNinja Docker volumes`
- `Initialize InvoiceNinja storage volume for ninja user`
- `Start football club stack`

- [ ] **Step 6: Add task-level become in Caddy role and handler**

In `ansible/roles/caddy/tasks/main.yml`, add `become: true` to:

- `Install Caddy`
- `Ensure Caddy backup directory exists`
- `Check current Caddyfile`
- `Back up existing Caddyfile before first Ansible takeover`
- `Render managed Caddyfile`
- `Ensure Caddy service is enabled and running`

Do not add `become: true` to `Validate Caddy config` because the managed Caddyfile is mode `0644`.

In `ansible/roles/caddy/handlers/main.yml`, change handler to:

```yaml
---
- name: Reload Caddy
  ansible.builtin.service:
    name: caddy
    state: reloaded
  become: true
```

- [ ] **Step 7: Add task-level become in backup role**

Change `ansible/roles/backup/tasks/main.yml` to:

```yaml
---
- name: Render backup script
  ansible.builtin.template:
    src: backup.sh.j2
    dest: "{{ football_club_project_dir }}/backup.sh"
    owner: root
    group: root
    mode: "0750"
  become: true

- name: Schedule daily football club backup
  ansible.builtin.cron:
    name: "football club daily backup"
    user: root
    minute: "0"
    hour: "2"
    job: "{{ football_club_project_dir }}/backup.sh >> /var/log/football-backup.log 2>&1"
  become: true
```

- [ ] **Step 8: Run unit contract tests and verify green phase**

Run:

```bash
python3 -m unittest tests/test_ansible_foundation.py
```

Expected: PASS.

## Task 3: Update project workflow documentation and run quality gates

**Files:**

- Modify: `AGENTS.md`

- [ ] **Step 1: Update workflow rule**

In `AGENTS.md`, under `## Workflow Rules`, add this bullet after the existing Ansible checks bullet:

```markdown
- Ansible playbooks must avoid global/play-level `become`; use task-level `become: true` only for operations that require root.
```

- [ ] **Step 2: Run all verification commands**

Run from repo root:

```bash
python3 -m unittest tests/test_ansible_foundation.py
ansible-lint
yamllint .
ansible-playbook ansible/playbooks/site.yml --syntax-check
ansible-playbook ansible/playbooks/validate.yml --syntax-check
```

Expected: all commands pass.

- [ ] **Step 3: Run dry-run if VM is reachable**

Run:

```bash
ansible-playbook ansible/playbooks/site.yml --check --diff
```

Expected if VM reachable: playbook completes without privilege escalation errors. If VM is not reachable or sudo credentials are unavailable, report the exact failure and do not claim dry-run success.

## Self-Review

- Spec coverage: all approved least-privilege requirements map to Tasks 1-3.
- Placeholder scan: no TBD, TODO, or unspecified implementation steps remain.
- Type/name consistency: file paths and task names match current repository files.
