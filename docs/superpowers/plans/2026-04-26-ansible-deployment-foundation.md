# Ansible Deployment Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable Ansible deployment foundation that provisions an Ubuntu LTS VM, renders the FK CĒSIS Docker Compose stack, manages Caddy, installs backups, and verifies the services with mandatory Ansible checks and HTTP smoke tests.

**Architecture:** Ansible owns host configuration and renders runtime files into `/opt/football-club`. Docker Compose remains the runtime orchestrator. Secrets are sourced only from Ansible Vault variables, with committed example files showing required names without real values.

**Tech Stack:** Ansible, Ansible Vault, ansible-lint, yamllint, Docker Engine, Docker Compose plugin, Caddy, Ubuntu LTS, Bash.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`
- Current platform plan: `docs/implementation-plan.md`
- Project instructions: `AGENTS.md`

## Scope

Implement Phase 1 deployment foundation only.

Included:

- Ansible project skeleton.
- Inventories for local VM and future production.
- Group variables and encrypted-vault workflow examples.
- Docker and Compose installation role.
- Football club Compose stack role.
- Caddy installation and full Caddyfile ownership role.
- Backup script and cron role.
- Validation playbook for compose, Caddy, containers, and HTTP smoke checks.
- Documentation for setup and verification commands.

Excluded:

- Member import automation.
- Stripe verification automation.
- n8n workflow creation.
- Application API bootstrapping.
- WhatsApp, OCR, Docuseal agreement automation.
- Regenerating `docs/html/implementation-plan.html`.

## File Structure

Create or modify these files:

```text
.ansible-lint
.yamllint.yml
.gitignore
AGENTS.md
docs/implementation-plan.md
docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md
ansible/ansible.cfg
ansible/requirements.yml
ansible/README.md
ansible/inventories/local_vm/hosts.yml
ansible/inventories/production/hosts.yml
ansible/inventories/local_vm/group_vars/local_vm/vars.yml
ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml
ansible/inventories/local_vm/group_vars/local_vm/vault.yml
ansible/inventories/production/group_vars/production/vars.yml
ansible/inventories/production/group_vars/production/vault.example.yml
ansible/playbooks/site.yml
ansible/playbooks/validate.yml
ansible/roles/common/tasks/main.yml
ansible/roles/docker/tasks/main.yml
ansible/roles/football_club_stack/tasks/main.yml
ansible/roles/caddy/tasks/main.yml
ansible/roles/caddy/handlers/main.yml
ansible/roles/backup/tasks/main.yml
ansible/roles/football_club_stack/templates/docker-compose.yml.j2
ansible/roles/football_club_stack/templates/env.j2
ansible/roles/caddy/templates/Caddyfile.j2
ansible/roles/backup/templates/backup.sh.j2
```

Responsibilities:

- `ansible.cfg`: default inventory, roles path, lint-friendly Ansible defaults.
- `requirements.yml`: pinned external Ansible collections required by the playbooks.
- `inventories/*/hosts.yml`: environment host definitions.
- `inventories/*/group_vars/*/vars.yml`: non-secret environment variables.
- `inventories/*/group_vars/*/vault.example.yml`: required secret variable names with safe dummy values.
- `inventories/local_vm/group_vars/local_vm/vault.yml`: encrypted local VM secrets for test deployment only.
- `site.yml`: main provision-and-deploy playbook.
- `validate.yml`: post-deploy runtime checks.
- `common`: baseline apt packages and directories.
- `docker`: Docker repository, engine, compose plugin, service enablement.
- `football_club_stack`: project files and stack lifecycle.
- `caddy`: Caddy install, old config backup, managed Caddyfile, validation, reload.
- `backup`: backup script and cron.

## Design Decisions

1. **Use Ansible instead of Terraform/OpenTofu now.**
   - Why: current target is an existing or local Ubuntu host over SSH, not cloud resource creation. Ansible directly solves host state, service files, Caddy, and Docker setup with low operational complexity.

2. **Keep Docker Compose as runtime orchestrator.**
   - Why: existing platform plan is Compose-based, each service already publishes an official image, and the club does not need Kubernetes-level complexity.

3. **Ansible owns the full Caddyfile.**
   - Why: user approved takeover after backup. Full ownership avoids hidden manual routes and makes validation deterministic.

4. **Secrets come from Ansible Vault only.**
   - Why: the generated `/opt/football-club/.env` must exist on the host, but no plaintext secrets may enter git history.

5. **Separate `site.yml` and `validate.yml`.**
   - Why: provisioning should be idempotent and validation should be rerunnable without changing host state except harmless service checks.

6. **Mandatory local linting from first Ansible change.**
   - Why: repo starts without executable tests; Ansible lint, YAML lint, syntax check, dry run, and VM apply become the first quality gates.

## Test Strategy

Framework/tools:

- `ansible-lint`
- `yamllint`
- `ansible-playbook --syntax-check`
- `ansible-playbook --check --diff`
- `ansible-playbook ansible/playbooks/site.yml`
- `ansible-playbook ansible/playbooks/validate.yml`

What to test:

- Static Ansible/YAML correctness.
- Playbook syntax.
- Dry-run support where modules allow check mode.
- Ubuntu VM provisioning succeeds.
- Docker Compose config renders and validates on target.
- Caddy config validates and service reload succeeds.
- Expected containers are present and running/healthy where possible.
- HTTP smoke checks return successful responses on real subdomains.

What not to test now:

- Stripe payment flows.
- Member import data correctness.
- n8n workflow logic.
- WhatsApp callbacks.
- DocTR OCR accuracy.

Acceptance criteria per unit are listed in each task below.

---

## Task 1: Add Ansible tooling configuration

**Files:**

- Create: `.ansible-lint`
- Create: `.yamllint.yml`
- Create: `ansible/ansible.cfg`
- Create: `ansible/requirements.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Create lint config files**

Create `.ansible-lint` with this content:

```yaml
---
profile: production
skip_list: []
warn_list: []
exclude_paths:
  - .git/
  - docs/html/
```

Create `.yamllint.yml` with this content:

```yaml
---
extends: default

rules:
  line-length:
    max: 120
    level: warning
  comments:
    min-spaces-from-content: 1
  document-start:
    present: true
```

- [ ] **Step 2: Create Ansible config**

Create `ansible/ansible.cfg` with this content:

```ini
[defaults]
inventory = inventories/local_vm/hosts.yml
roles_path = roles
stdout_callback = default
callback_result_format = yaml
bin_ansible_callbacks = True
host_key_checking = True
retry_files_enabled = False
interpreter_python = auto_silent

[privilege_escalation]
become = True
become_method = sudo
become_ask_pass = False
```

- [ ] **Step 3: Create requirements file**

Create `ansible/requirements.yml` with this content:

```yaml
---
collections:
  - name: community.docker
    version: "4.3.1"
  - name: ansible.posix
    version: "2.0.0"
```

- [ ] **Step 4: Update `.gitignore`**

If `.gitignore` does not exist, create it. Ensure it contains exactly these deployment-secret rules, preserving any existing unrelated entries:

```gitignore
# Local Ansible secrets and runtime artifacts
.ansible/
*.retry
.vault-pass
vault-pass.txt
ansible/inventories/*/group_vars/*/vault.local.yml

# Generated service secrets must never be committed
.env
/opt/football-club/.env

# Real identity documents must never be committed
*.id-photo.jpg
*.id-photo.jpeg
*.id-photo.png
```

Do not ignore `ansible/inventories/*/group_vars/*/vault.yml`; those files are intended to be committed only after encryption.

- [ ] **Step 5: Run static checks**

Run:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
ansible-lint
yamllint .
```

Expected:

- `ansible-galaxy` installs required collections or reports they are already installed.
- `ansible-lint` may fail because playbooks are not created yet; if it fails only for missing playbooks, continue.
- `yamllint .` passes for files created in this task.

- [ ] **Step 6: Commit**

```bash
git add .ansible-lint .yamllint.yml .gitignore ansible/ansible.cfg ansible/requirements.yml
git commit -m "chore: add ansible tooling config"
```

Acceptance criteria:

- Lint configuration files exist.
- Ansible config points to local VM inventory.
- Required collections are declared.
- `.gitignore` blocks local secret files without blocking encrypted `vault.yml`.

---

## Task 2: Add inventories and variable contracts

**Files:**

- Create: `ansible/inventories/local_vm/hosts.yml`
- Create: `ansible/inventories/production/hosts.yml`
- Create: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`
- Create: `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`
- Create: `ansible/inventories/local_vm/group_vars/local_vm/vault.yml`
- Create: `ansible/inventories/production/group_vars/production/vars.yml`
- Create: `ansible/inventories/production/group_vars/production/vault.example.yml`

- [ ] **Step 1: Create local VM inventory**

Create `ansible/inventories/local_vm/hosts.yml`:

```yaml
---
all:
  children:
    local_vm:
      children:
        football_club:
          hosts:
            local-vm:
              ansible_host: 192.0.2.10
              ansible_user: ubuntu
```

`192.0.2.10` is documentation-safe placeholder IP. Before real execution, replace it with the local VM IP.

- [ ] **Step 2: Create production inventory**

Create `ansible/inventories/production/hosts.yml`:

```yaml
---
all:
  children:
    production:
      children:
        football_club:
          hosts:
            production:
              ansible_host: 203.0.113.10
              ansible_user: ubuntu
```

`203.0.113.10` is documentation-safe placeholder IP. Do not run production until this is replaced with the real host.

- [ ] **Step 3: Create local VM non-secret vars**

Create `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`:

```yaml
---
football_club_domain: "example.lv"
football_club_admin_email: "admin@example.lv"
football_club_project_dir: "/opt/football-club"
football_club_backup_dir: "/opt/backups/football-club"
football_club_backup_remote: "user@offsite-host:/backups/football-club/"
football_club_timezone: "Europe/Riga"
football_club_caddyfile_path: "/etc/caddy/Caddyfile"
football_club_caddy_backup_dir: "/etc/caddy/backups"
football_club_compose_project_name: "football-club"
football_club_doctr_enabled: false
```

Before real local execution, set `football_club_domain` to the real domain whose subdomains point to the VM.

- [ ] **Step 4: Create production non-secret vars**

Create `ansible/inventories/production/group_vars/production/vars.yml` with the same keys:

```yaml
---
football_club_domain: "example.lv"
football_club_admin_email: "admin@example.lv"
football_club_project_dir: "/opt/football-club"
football_club_backup_dir: "/opt/backups/football-club"
football_club_backup_remote: "user@offsite-host:/backups/football-club/"
football_club_timezone: "Europe/Riga"
football_club_caddyfile_path: "/etc/caddy/Caddyfile"
football_club_caddy_backup_dir: "/etc/caddy/backups"
football_club_compose_project_name: "football-club"
football_club_doctr_enabled: false
```

- [ ] **Step 5: Create vault example files**

Create `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`:

```yaml
---
vault_doli_db_password: "change-me"
vault_doli_db_root_password: "change-me"
vault_doli_admin_password: "change-me"
vault_ninja_app_key: "base64:change-me"
vault_ninja_admin_password: "change-me"
vault_ninja_db_password: "change-me"
vault_ninja_db_root_password: "change-me"
vault_n8n_encryption_key: "change-me-32-characters-minimum"
vault_n8n_db_password: "change-me"
vault_docuseal_secret_key: "change-me-64-characters-minimum"
vault_stripe_publishable_key: "pk_test_change_me"
vault_stripe_secret_key: "sk_test_change_me"
vault_stripe_webhook_secret: "whsec_change_me"
```

Create `ansible/inventories/production/group_vars/production/vault.example.yml` with identical content.

- [ ] **Step 6: Create encrypted local VM vault**

Create a temporary plaintext file outside the repo:

```bash
cp ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml /tmp/fk-cesis-local-vault.yml
```

Edit `/tmp/fk-cesis-local-vault.yml` and replace dummy values with local test secrets. Then encrypt it into the repo:

```bash
ansible-vault encrypt /tmp/fk-cesis-local-vault.yml --output ansible/inventories/local_vm/group_vars/local_vm/vault.yml
rm /tmp/fk-cesis-local-vault.yml
```

Expected first line of `ansible/inventories/local_vm/group_vars/local_vm/vault.yml`:

```text
$ANSIBLE_VAULT;1.1;AES256
```

Do not create production `vault.yml` until production secrets exist.

- [ ] **Step 7: Run checks**

Run:

```bash
yamllint ansible/inventories
ansible-inventory -i ansible/inventories/local_vm/hosts.yml --list
```

Expected:

- `yamllint` passes.
- `ansible-inventory` lists group `football_club` and host `local-vm`.

- [ ] **Step 8: Commit**

```bash
git add ansible/inventories
git commit -m "chore: add ansible inventories and vars"
```

Acceptance criteria:

- Local and production inventory structure exists.
- Non-secret vars are separated from secrets.
- Local `vault.yml` is encrypted before staging.
- Production example exists without real production secrets.

---

## Task 3: Implement baseline and Docker roles

**Files:**

- Create: `ansible/playbooks/site.yml`
- Create: `ansible/roles/common/tasks/main.yml`
- Create: `ansible/roles/docker/tasks/main.yml`

- [ ] **Step 1: Create site playbook shell**

Create `ansible/playbooks/site.yml`:

```yaml
---
- name: Provision FK CĒSIS football club platform
  hosts: football_club
  become: true
  gather_facts: true

  roles:
    - role: common
    - role: docker
```

- [ ] **Step 2: Create common role**

Create `ansible/roles/common/tasks/main.yml`:

```yaml
---
- name: Ensure apt cache is up to date
  ansible.builtin.apt:
    update_cache: true
    cache_valid_time: 3600

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

- name: Ensure project directory exists
  ansible.builtin.file:
    path: "{{ football_club_project_dir }}"
    state: directory
    owner: root
    group: root
    mode: "0755"

- name: Ensure backup root directory exists
  ansible.builtin.file:
    path: "{{ football_club_backup_dir }}"
    state: directory
    owner: root
    group: root
    mode: "0750"
```

- [ ] **Step 3: Create Docker role**

Create `ansible/roles/docker/tasks/main.yml`:

```yaml
---
- name: Install Docker packages from Ubuntu repositories
  ansible.builtin.apt:
    name:
      - docker.io
      - docker-compose-v2
    state: present

- name: Ensure Docker service is enabled and running
  ansible.builtin.service:
    name: docker
    enabled: true
    state: started
```

This uses Ubuntu LTS repository packages for simplicity and repeatability. If package `docker-compose-v2` is unavailable on the selected Ubuntu LTS VM, replace it with `docker-compose-plugin` only after confirming the VM package name with `apt-cache policy`.

- [ ] **Step 4: Syntax-check playbook**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
```

Expected:

```text
playbook: ansible/playbooks/site.yml
```

- [ ] **Step 5: Run lint checks**

Run:

```bash
ansible-lint ansible/playbooks/site.yml
yamllint ansible
```

Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add ansible/playbooks/site.yml ansible/roles/common/tasks/main.yml ansible/roles/docker/tasks/main.yml
git commit -m "feat: provision baseline docker host"
```

Acceptance criteria:

- `site.yml` can syntax-check.
- Baseline directories are defined.
- Docker service is installed and enabled by role.

---

## Task 4: Implement Compose stack templates and role

**Files:**

- Modify: `ansible/playbooks/site.yml`
- Create: `ansible/roles/football_club_stack/tasks/main.yml`
- Create: `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`
- Create: `ansible/roles/football_club_stack/templates/env.j2`

- [ ] **Step 1: Add stack role to site playbook**

Modify `ansible/playbooks/site.yml`:

```yaml
---
- name: Provision FK CĒSIS football club platform
  hosts: football_club
  become: true
  gather_facts: true

  roles:
    - role: common
    - role: docker
    - role: football_club_stack
```

- [ ] **Step 2: Create Compose template**

Create `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`:

```yaml
services:
  dolibarr:
    image: dolibarr/dolibarr:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8081:80"
    environment:
      DOLI_DB_HOST: dolibarr-db
      DOLI_DB_NAME: dolibarr
      DOLI_DB_USER: dolibarr
      DOLI_DB_PASSWORD: ${DOLI_DB_PASSWORD}
      DOLI_ADMIN_LOGIN: admin
      DOLI_ADMIN_PASSWORD: ${DOLI_ADMIN_PASSWORD}
      DOLI_URL_ROOT: https://club.${DOMAIN}
      DOLI_AUTH: dolibarr
    volumes:
      - dolibarr_data:/var/www/html/documents
    depends_on:
      - dolibarr-db

  dolibarr-db:
    image: mariadb:10.6
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: dolibarr
      MYSQL_USER: dolibarr
      MYSQL_PASSWORD: ${DOLI_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DOLI_DB_ROOT_PASSWORD}
    volumes:
      - dolibarr_db_data:/var/lib/mysql

  invoiceninja:
    image: invoiceninja/invoiceninja-octane:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8082:80"
    environment:
      APP_ENV: production
      APP_DEBUG: "false"
      APP_URL: https://billing.${DOMAIN}
      APP_KEY: ${NINJA_APP_KEY}
      REQUIRE_HTTPS: "true"
      IS_DOCKER: "true"
      IN_USER_EMAIL: ${ADMIN_EMAIL}
      IN_PASSWORD: ${NINJA_ADMIN_PASSWORD}
      IN_USER: Admin
      DB_HOST: ninja-db
      DB_DATABASE: ninja
      DB_USERNAME: ninja
      DB_PASSWORD: ${NINJA_DB_PASSWORD}
      NINJA_LICENSE: self-hosted-open-source
    volumes:
      - ninja_storage:/app/storage
    depends_on:
      - ninja-db

  ninja-db:
    image: mariadb:10.6
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: ninja
      MYSQL_USER: ninja
      MYSQL_PASSWORD: ${NINJA_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${NINJA_DB_ROOT_PASSWORD}
    volumes:
      - ninja_db_data:/var/lib/mysql

  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      N8N_HOST: n8n.${DOMAIN}
      N8N_PORT: 5678
      WEBHOOK_URL: https://n8n.${DOMAIN}/
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: n8n-db
      DB_POSTGRESDB_DATABASE: n8n
      DB_POSTGRESDB_USER: n8n
      DB_POSTGRESDB_PASSWORD: ${N8N_DB_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - n8n-db

  n8n-db:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${N8N_DB_PASSWORD}
    volumes:
      - n8n_db_data:/var/lib/postgresql/data

  docuseal:
    image: docuseal/docuseal:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      SECRET_KEY_BASE: ${DOCUSEAL_SECRET_KEY}
      WORKDIR: /data
    volumes:
      - docuseal_data:/data

  doctr-api:
    image: ghcr.io/mindee/doctr:api-cpu-latest
    restart: "no"
    profiles:
      - ocr
    deploy:
      resources:
        limits:
          memory: 512m

volumes:
  dolibarr_data:
  dolibarr_db_data:
  ninja_storage:
  ninja_db_data:
  n8n_data:
  n8n_db_data:
  docuseal_data:
```

- [ ] **Step 3: Create env template**

Create `ansible/roles/football_club_stack/templates/env.j2`:

```jinja
DOMAIN={{ football_club_domain }}
DOLI_DB_PASSWORD={{ vault_doli_db_password }}
DOLI_DB_ROOT_PASSWORD={{ vault_doli_db_root_password }}
DOLI_ADMIN_PASSWORD={{ vault_doli_admin_password }}
NINJA_APP_KEY={{ vault_ninja_app_key }}
NINJA_ADMIN_PASSWORD={{ vault_ninja_admin_password }}
NINJA_DB_PASSWORD={{ vault_ninja_db_password }}
NINJA_DB_ROOT_PASSWORD={{ vault_ninja_db_root_password }}
N8N_ENCRYPTION_KEY={{ vault_n8n_encryption_key }}
N8N_DB_PASSWORD={{ vault_n8n_db_password }}
DOCUSEAL_SECRET_KEY={{ vault_docuseal_secret_key }}
STRIPE_PUBLISHABLE_KEY={{ vault_stripe_publishable_key }}
STRIPE_SECRET_KEY={{ vault_stripe_secret_key }}
STRIPE_WEBHOOK_SECRET={{ vault_stripe_webhook_secret }}
ADMIN_EMAIL={{ football_club_admin_email }}
```

- [ ] **Step 4: Create stack role tasks**

Create `ansible/roles/football_club_stack/tasks/main.yml`:

```yaml
---
- name: Render Docker Compose project
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ football_club_project_dir }}/docker-compose.yml"
    owner: root
    group: root
    mode: "0644"

- name: Render environment file from Ansible Vault values
  ansible.builtin.template:
    src: env.j2
    dest: "{{ football_club_project_dir }}/.env"
    owner: root
    group: root
    mode: "0600"
  no_log: true

- name: Validate rendered Docker Compose config
  ansible.builtin.command:
    cmd: docker compose -f {{ football_club_project_dir }}/docker-compose.yml --env-file {{ football_club_project_dir }}/.env config
  register: compose_config_result
  changed_when: false
  no_log: true

- name: Prepare InvoiceNinja Docker volumes
  ansible.builtin.command:
    cmd: docker volume create {{ football_club_compose_project_name }}_ninja_storage
  register: football_club_stack_ninja_storage_volume_result
  changed_when: >
    football_club_stack_ninja_storage_volume_result.stdout ==
    football_club_compose_project_name ~ '_ninja_storage'

- name: Initialize InvoiceNinja storage volume for ninja user
  ansible.builtin.command:
    cmd: >
      docker run --rm
      -v {{ football_club_compose_project_name }}_ninja_storage:/mnt/ninja-volume
      alpine:3.20
      sh -c 'mkdir -p
      /mnt/ninja-volume/framework/cache/data
      /mnt/ninja-volume/framework/sessions
      /mnt/ninja-volume/framework/views
      /mnt/ninja-volume/logs
      && chown -R 999:999 /mnt/ninja-volume
      && chmod -R u+rwX,g+rwX,o-rwx /mnt/ninja-volume'
  changed_when: false

- name: Start football club stack
  ansible.builtin.command:
    cmd: docker compose -p {{ football_club_compose_project_name }} -f {{ football_club_project_dir }}/docker-compose.yml --env-file {{ football_club_project_dir }}/.env up -d
  register: compose_up_result
  changed_when: "'Started' in compose_up_result.stderr or 'Created' in compose_up_result.stderr or 'Recreated' in compose_up_result.stderr"
  no_log: true
```

- [ ] **Step 5: Run checks**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ansible-lint ansible/playbooks/site.yml
yamllint ansible
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ansible/playbooks/site.yml ansible/roles/football_club_stack/tasks/main.yml ansible/roles/football_club_stack/templates/docker-compose.yml.j2 ansible/roles/football_club_stack/templates/env.j2
git commit -m "feat: render football club compose stack"
```

Acceptance criteria:

- Compose and env templates exist.
- `.env` renders with `0600` mode and `no_log`.
- Compose config validation is part of the role.
- Stack starts through Docker Compose.

---

## Task 5: Implement Caddy role

**Files:**

- Modify: `ansible/playbooks/site.yml`
- Create: `ansible/roles/caddy/tasks/main.yml`
- Create: `ansible/roles/caddy/handlers/main.yml`
- Create: `ansible/roles/caddy/templates/Caddyfile.j2`

- [ ] **Step 1: Add Caddy role to site playbook**

Modify `ansible/playbooks/site.yml`:

```yaml
---
- name: Provision FK CĒSIS football club platform
  hosts: football_club
  become: true
  gather_facts: true

  roles:
    - role: common
    - role: docker
    - role: football_club_stack
    - role: caddy
```

- [ ] **Step 2: Create Caddyfile template**

Create `ansible/roles/caddy/templates/Caddyfile.j2`:

```caddyfile
{
  email {{ football_club_admin_email }}
}

club.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:8081
}

billing.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:8082
}

n8n.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:5678
}

agreements.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:3000
}
```

Caddy proxies to host-local Compose ports, not Docker service names, because host Caddy runs outside the Compose network.

- [ ] **Step 3: Create Caddy role tasks**

Create `ansible/roles/caddy/tasks/main.yml`:

```yaml
---
- name: Install Caddy
  ansible.builtin.apt:
    name: caddy
    state: present
    update_cache: true

- name: Ensure Caddy backup directory exists
  ansible.builtin.file:
    path: "{{ football_club_caddy_backup_dir }}"
    state: directory
    owner: root
    group: root
    mode: "0750"

- name: Check current Caddyfile
  ansible.builtin.stat:
    path: "{{ football_club_caddyfile_path }}"
  register: caddyfile_stat

- name: Back up existing Caddyfile before first Ansible takeover
  ansible.builtin.copy:
    src: "{{ football_club_caddyfile_path }}"
    dest: "{{ football_club_caddy_backup_dir }}/Caddyfile.pre-ansible"
    owner: root
    group: root
    mode: "0640"
    remote_src: true
    force: false
  when: caddyfile_stat.stat.exists

- name: Render managed Caddyfile
  ansible.builtin.template:
    src: Caddyfile.j2
    dest: "{{ football_club_caddyfile_path }}"
    owner: root
    group: root
    mode: "0644"
  notify: Reload Caddy

- name: Validate Caddy config
  ansible.builtin.command:
    cmd: caddy validate --config {{ football_club_caddyfile_path }}
  register: caddy_validate_result
  changed_when: false

- name: Ensure Caddy service is enabled and running
  ansible.builtin.service:
    name: caddy
    enabled: true
    state: started
```

Create `ansible/roles/caddy/handlers/main.yml`:

```yaml
---
- name: Reload Caddy
  ansible.builtin.service:
    name: caddy
    state: reloaded
```

- [ ] **Step 4: Run checks**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ansible-lint ansible/playbooks/site.yml
yamllint ansible
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ansible/playbooks/site.yml ansible/roles/caddy
git commit -m "feat: manage caddy reverse proxy"
```

Acceptance criteria:

- Caddy installs through Ansible.
- Existing Caddyfile is backed up once.
- Managed Caddyfile proxies to host-local Compose ports.
- Caddy config validates before completion.

---

## Task 6: Implement backup role

**Files:**

- Modify: `ansible/playbooks/site.yml`
- Create: `ansible/roles/backup/tasks/main.yml`
- Create: `ansible/roles/backup/templates/backup.sh.j2`

- [ ] **Step 1: Add backup role to site playbook**

Modify `ansible/playbooks/site.yml`:

```yaml
---
- name: Provision FK CĒSIS football club platform
  hosts: football_club
  become: true
  gather_facts: true

  roles:
    - role: common
    - role: docker
    - role: football_club_stack
    - role: caddy
    - role: backup
```

- [ ] **Step 2: Create backup script template**

Create `ansible/roles/backup/templates/backup.sh.j2`:

```jinja
#!/bin/bash
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="{{ football_club_backup_dir }}/${DATE}"
PROJECT_DIR="{{ football_club_project_dir }}"
COMPOSE="docker compose -p {{ football_club_compose_project_name }} -f ${PROJECT_DIR}/docker-compose.yml --env-file ${PROJECT_DIR}/.env"

mkdir -p "${BACKUP_DIR}"

cd "${PROJECT_DIR}"

${COMPOSE} exec -T dolibarr-db sh -c 'mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" dolibarr' > "${BACKUP_DIR}/dolibarr.sql"
${COMPOSE} exec -T ninja-db sh -c 'mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" ninja' > "${BACKUP_DIR}/ninja.sql"
${COMPOSE} exec -T n8n-db sh -c 'PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump -U n8n n8n' > "${BACKUP_DIR}/n8n.sql"

docker run --rm -v {{ football_club_compose_project_name }}_dolibarr_data:/data:ro -v "${BACKUP_DIR}":/backup alpine \
  tar czf /backup/dolibarr_documents.tar.gz -C /data .

docker run --rm -v {{ football_club_compose_project_name }}_n8n_data:/data:ro -v "${BACKUP_DIR}":/backup alpine \
  tar czf /backup/n8n_workflows.tar.gz -C /data .

rsync -az "${BACKUP_DIR}" "{{ football_club_backup_remote }}"

find "{{ football_club_backup_dir }}" -maxdepth 1 -mtime +30 -type d -exec rm -rf {} +

echo "Backup complete: ${BACKUP_DIR}"
```

- [ ] **Step 3: Create backup role tasks**

Create `ansible/roles/backup/tasks/main.yml`:

```yaml
---
- name: Render backup script
  ansible.builtin.template:
    src: backup.sh.j2
    dest: "{{ football_club_project_dir }}/backup.sh"
    owner: root
    group: root
    mode: "0750"

- name: Schedule daily football club backup
  ansible.builtin.cron:
    name: "football club daily backup"
    user: root
    minute: "0"
    hour: "2"
    job: "{{ football_club_project_dir }}/backup.sh >> /var/log/football-backup.log 2>&1"
```

- [ ] **Step 4: Run checks**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ansible-lint ansible/playbooks/site.yml
yamllint ansible
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ansible/playbooks/site.yml ansible/roles/backup
git commit -m "feat: install backup automation"
```

Acceptance criteria:

- Backup script is rendered executable by root.
- Cron schedule exists.
- Script backs up Dolibarr DB, InvoiceNinja DB, n8n DB, Dolibarr documents, and n8n data.
- Script syncs to configured offsite target.

---

## Task 7: Add validation playbook

**Files:**

- Create: `ansible/playbooks/validate.yml`

- [ ] **Step 1: Create validation playbook**

Create `ansible/playbooks/validate.yml`:

```yaml
---
- name: Validate FK CĒSIS football club platform deployment
  hosts: football_club
  become: true
  gather_facts: false

  tasks:
    - name: Validate Docker Compose config
      ansible.builtin.command:
        cmd: docker compose -f {{ football_club_project_dir }}/docker-compose.yml --env-file {{ football_club_project_dir }}/.env config
      register: validate_compose_config
      changed_when: false
      no_log: true

    - name: List Compose services
      ansible.builtin.command:
        cmd: docker compose -p {{ football_club_compose_project_name }} -f {{ football_club_project_dir }}/docker-compose.yml --env-file {{ football_club_project_dir }}/.env ps --format json
      register: compose_ps
      changed_when: false
      no_log: true

    - name: Validate Caddy config
      ansible.builtin.command:
        cmd: caddy validate --config {{ football_club_caddyfile_path }}
      register: validate_caddy
      changed_when: false

    - name: Check Dolibarr HTTP endpoint
      ansible.builtin.uri:
        url: "https://club.{{ football_club_domain }}/"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check InvoiceNinja HTTP endpoint
      ansible.builtin.uri:
        url: "https://billing.{{ football_club_domain }}/"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check n8n HTTP endpoint
      ansible.builtin.uri:
        url: "https://n8n.{{ football_club_domain }}/"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check Docuseal HTTP endpoint
      ansible.builtin.uri:
        url: "https://agreements.{{ football_club_domain }}/"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false
```

- [ ] **Step 2: Run static checks**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
ansible-lint ansible/playbooks/validate.yml
yamllint ansible
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add ansible/playbooks/validate.yml
git commit -m "test: add deployment validation playbook"
```

Acceptance criteria:

- Validation playbook verifies Compose config.
- Validation playbook verifies Caddy config.
- Validation playbook checks all four public service domains.

---

## Task 8: Add operator documentation

**Files:**

- Create: `ansible/README.md`
- Modify: `AGENTS.md`
- Modify: `docs/implementation-plan.md`

- [ ] **Step 1: Create Ansible README**

Create `ansible/README.md`:

```markdown
# FK CĒSIS Ansible Deployment

This directory deploys the Phase 1 foundation for the FK CĒSIS club platform.

## Requirements

Control machine:

- Ansible
- ansible-lint
- yamllint

Install collections:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

## Local VM setup

1. Create an Ubuntu LTS VM.
2. Ensure SSH works for the inventory user.
3. Point these real DNS names to the VM IP:
   - `club.<domain>`
   - `billing.<domain>`
   - `n8n.<domain>`
   - `agreements.<domain>`
4. Update `ansible/inventories/local_vm/hosts.yml` with the VM IP.
5. Update `ansible/inventories/local_vm/group_vars/local_vm/vars.yml` with the real domain and admin email.
6. Create encrypted `ansible/inventories/local_vm/group_vars/local_vm/vault.yml` from `vault.example.yml`.

## Required checks

Run every time Ansible changes:

```bash
ansible-lint
yamllint .
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
```

Run before applying:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff ansible/playbooks/site.yml --ask-vault-pass
```

Apply to local VM:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/site.yml --ask-vault-pass
```

Validate deployment:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/validate.yml --ask-vault-pass
```

## Secret rules

Never commit plaintext secrets, vault passwords, generated `.env` files, API tokens, Stripe secrets, WhatsApp tokens, database passwords, or real ID document photos.
```

- [ ] **Step 2: Verify AGENTS.md deployment rules**

Confirm `AGENTS.md` contains:

```markdown
- For Ansible changes, `ansible-lint`, `yamllint`, and `ansible-playbook --syntax-check` are mandatory.
- For deployment changes, also run `ansible-playbook --check --diff` and apply to the Ubuntu LTS VM before claiming completion.
```

- [ ] **Step 3: Verify implementation plan acceptance checks**

Confirm `docs/implementation-plan.md` Phase 1 lists Ansible acceptance checks before HTTP checks.

- [ ] **Step 4: Run docs-safe checks**

Run:

```bash
yamllint ansible .yamllint.yml
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add ansible/README.md AGENTS.md docs/implementation-plan.md
git commit -m "docs: document ansible deployment workflow"
```

Acceptance criteria:

- Operator has exact setup, dry-run, apply, and validation commands.
- Secret rules are documented.
- Project workflow rules match implementation requirements.

---

## Task 9: Full local VM verification

**Files:**

- Modify only if verification exposes defects in earlier files.

- [ ] **Step 1: Install collections**

Run:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

Expected: collections installed or already present.

- [ ] **Step 2: Run mandatory static checks**

Run:

```bash
ansible-lint
yamllint .
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
```

Expected: all pass.

- [ ] **Step 3: Run dry-run**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff ansible/playbooks/site.yml --ask-vault-pass
```

Expected: play completes without failed tasks. Tasks that cannot fully predict Docker runtime changes in check mode must not fail.

- [ ] **Step 4: Apply to Ubuntu LTS VM**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/site.yml --ask-vault-pass
```

Expected: play completes with `failed=0`.

- [ ] **Step 5: Validate deployment**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/validate.yml --ask-vault-pass
```

Expected: play completes with `failed=0`.

- [ ] **Step 6: Record verification results**

Create or update `docs/superpowers/plans/2026-04-26-ansible-deployment-foundation-verification.md` with:

```markdown
# Ansible Deployment Foundation Verification

Date: 2026-04-26
Target: local Ubuntu LTS VM

## Commands

- ansible-lint: PASS
- yamllint .: PASS
- site syntax-check: PASS
- validate syntax-check: PASS
- site check/diff: PASS
- site apply: PASS
- validate playbook: PASS

## Notes

- Domain used: <domain>
- VM OS/version: <Ubuntu version>
- Any deviations: none
```

Replace `<domain>` and `<Ubuntu version>` with actual values. If any deviation exists, document it clearly.

- [ ] **Step 7: Commit verification record and fixes**

```bash
git add docs/superpowers/plans/2026-04-26-ansible-deployment-foundation-verification.md ansible AGENTS.md docs/implementation-plan.md
git commit -m "test: verify ansible deployment foundation"
```

Acceptance criteria:

- All mandatory checks pass.
- VM apply succeeds.
- Runtime validation succeeds.
- Verification evidence is documented.

---

## Final Review Checklist

Before claiming completion:

- [ ] No plaintext secrets are present in git diff.
- [ ] `ansible/inventories/local_vm/group_vars/local_vm/vault.yml` starts with `$ANSIBLE_VAULT;` if committed.
- [ ] `docs/html/implementation-plan.html` is unchanged.
- [ ] `ansible-lint` passes.
- [ ] `yamllint .` passes.
- [ ] `ansible-playbook --syntax-check` passes for `site.yml` and `validate.yml`.
- [ ] `ansible-playbook --check --diff` passes against the Ubuntu LTS VM.
- [ ] Full Ansible apply passes against the Ubuntu LTS VM.
- [ ] Validation playbook passes.
- [ ] Phase 1 manual Stripe Latvia SEPA/card gate remains documented and not bypassed.

## Plan Self-Review

Spec coverage:

- Ubuntu LTS VM over SSH: covered by inventories, README, Task 9.
- Docker + Compose install: covered by Task 3.
- `/opt/football-club` Compose and env rendering: covered by Task 4.
- Ansible Vault secrets: covered by Task 2 and Task 4.
- Caddy ownership and backup: covered by Task 5.
- Backup script and cron: covered by Task 6.
- Mandatory checks: covered by Tasks 1, 3-9.
- HTTP smoke checks: covered by Task 7 and Task 9.
- HTML companion stale: covered by final checklist and docs scope.

Placeholder scan:

- No incomplete placeholders are intentionally left.
- Documentation-safe placeholder IPs and domains are explicitly marked as values to replace before execution.

Consistency check:

- Variable names in `vars.yml`, `vault.example.yml`, `env.j2`, and templates match.
- Playbook names and commands are consistent across README and tasks.
