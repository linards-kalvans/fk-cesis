# MMS Unified Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move FK Cēsis MMS from standalone manual runtime into the existing Ansible-managed Docker Compose stack with internal InvoiceNinja and Docuseal integration.

**Architecture:** Add MMS web, qcluster, and Postgres services to the existing `football_club_stack` role so all active apps share the default Compose network. Route inbound traffic through the existing Caddy managed snippet at `members.<domain>` / `members.lan`, while MMS calls InvoiceNinja and Docuseal through internal service URLs. Extend the existing env, backup, validation, inventory, and docs instead of adding a second deployment path.

**Tech Stack:** Ansible, Docker Compose, Caddy, PostgreSQL, Django/Gunicorn MMS image, InvoiceNinja, Docuseal, Bash backup script, YAML/Jinja templates.

---

## Design decisions

1. **Keep one Compose project.**
   - Why: MMS needs service-to-service access to InvoiceNinja and Docuseal. Putting all services in `ansible/roles/football_club_stack/templates/docker-compose.yml.j2` gives Compose DNS names (`nginx`, `docuseal`, `mms-postgres`) without external Docker network plumbing.

2. **Use existing host port proxy pattern.**
   - Why: Current Caddy routes proxy to loopback ports (`8089`, `3039`). Adding `127.0.0.1:8000:8000` for MMS is the smallest consistent change and keeps Caddy ownership unchanged.

3. **Render MMS settings into the existing `.env`.**
   - Why: The stack already renders one Vault-backed env file from `ansible/roles/football_club_stack/templates/env.j2`. Extending that file avoids a second secret path and keeps `docker compose --env-file` behavior unchanged.

4. **Use internal integration URLs.**
   - Why: `INVOICE_NINJA_API_URL=http://nginx` and `DOCUSEAL_API_URL=http://docuseal:3000` keep integration traffic inside the Docker network and avoid public TLS/Caddy hairpin failures.

5. **Keep image tag inventory-controlled.**
   - Why: The user approved `dev` for local VM and `main` for production. Inventory vars are the smallest existing mechanism for environment-specific values.

6. **Add one Ansible regression test file.**
   - Why: This repo already uses `ansible/tests/caddy_import_snippet.yml` as lightweight executable assertions. A new `ansible/tests/mms_unified_stack.yml` can verify templates and vars without a live host.

## File-by-file plan

### Create

- `ansible/tests/mms_unified_stack.yml`
  - Executable Ansible localhost assertions for MMS Compose services, internal URLs, Caddy route, env vars, backup coverage, validation endpoint, and inventory image tags.

### Modify

- `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`
  - Add `mms-postgres`, `mms-web`, `mms-qcluster`, and `mms_pgdata` volume.
  - Keep existing InvoiceNinja and Docuseal services unchanged except dependency interactions as needed.

- `ansible/roles/football_club_stack/templates/env.j2`
  - Add MMS env keys rendered from normal vars and Vault vars.

- `ansible/roles/football_club_stack/defaults/main.yml`
  - Add default MMS image, image tag, site URL, allowed hosts, DB name/user, and internal provider URLs.

- `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`
  - Add `football_club_stack_mms_image_tag: dev`.

- `ansible/inventories/production/group_vars/production/vars.yml`
  - Add `football_club_stack_mms_image_tag: main`.

- `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`
  - Add MMS placeholder secrets. Keep `ansible_become_password` existing.

- `ansible/inventories/production/group_vars/production/vault.example.yml`
  - Add same MMS placeholder secrets.

- `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
  - Add `members.{{ football_club_domain }}` proxy to `127.0.0.1:8000`.

- `ansible/roles/caddy/templates/Caddyfile-local.j2`
  - Add `members.lan` with `tls internal`, proxy to `127.0.0.1:8000`.

- `ansible/playbooks/validate.yml`
  - Add `members_endpoint` fact and HTTP check for `/healthz`.

- `ansible/roles/backup/templates/backup.sh.j2`
  - Add MMS Postgres dump and MMS upload/private upload tarballs.

- `ansible/README.md`
  - Add `members` DNS/hosts entries, MMS secret expectations, validation and backup scope.

- `docs/fk-cesis-mms-deployment.md`
  - Mark standalone deployment as legacy/manual and point to Ansible unified stack.

- `docs/implementation-plan.md`
  - Add MMS to active managed runtime, routes, backup, validation.

- `AGENTS.md`
  - Update repo scope and active service list to include MMS deployment integration.

## Test strategy

### Framework

Use existing Ansible-based test style under `ansible/tests/` with `ansible.builtin.slurp` and `ansible.builtin.assert`.

### Test file structure

Create `ansible/tests/mms_unified_stack.yml` with one localhost play:

- read templates and inventory files with `slurp`
- assert strings/regexes for required MMS integration points

### What to test

- Compose template defines `mms-postgres`, `mms-web`, `mms-qcluster`.
- Compose template maps MMS web on `127.0.0.1:8000:8000`.
- Compose template uses image `{{ football_club_stack_mms_image }}:{{ football_club_stack_mms_image_tag }}`.
- Compose template includes `mms_pgdata` volume.
- Env template includes MMS secrets and internal URLs.
- Caddy templates include `members` routes.
- Validation playbook checks `members` `/healthz`.
- Backup script dumps MMS Postgres and archives MMS upload data.
- Local inventory sets tag `dev`; production inventory sets tag `main`.
- Vault examples include MMS placeholders.

### What not to test

- MMS application internals.
- Live InvoiceNinja/Docuseal API calls.
- Production deployment apply.
- Standalone MMS data migration.
- Docker image availability at Codeberg.

## Acceptance criteria per unit

1. **Regression test unit**
   - Running `ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml` fails before implementation and passes after implementation.

2. **Compose/env unit**
   - Rendered Compose contains MMS web, qcluster, Postgres, internal network service references, and persistent volumes.
   - Rendered `.env` includes MMS config with live provider modes and Vault-backed secrets.

3. **Routing/validation unit**
   - Caddy snippets contain `members.<domain>` and `members.lan`.
   - Validation playbook checks the `members` `/healthz` endpoint.

4. **Backup unit**
   - Backup script writes MMS DB dump and archives upload/private upload data.

5. **Docs unit**
   - Docs present Ansible unified stack as source of truth.
   - Standalone MMS docs are clearly legacy/manual.

## Documentation scope

Update only active source-of-truth docs and role guidance:

- `ansible/README.md`
- `docs/fk-cesis-mms-deployment.md`
- `docs/implementation-plan.md`
- `AGENTS.md`

Do not regenerate `docs/html/implementation-plan.html`; AGENTS.md says rendered HTML may be stale and should only regenerate when explicitly in scope.

---

## Task 1: Add failing MMS unified stack regression test

**Files:**
- Create: `ansible/tests/mms_unified_stack.yml`

- [ ] **Step 1: Create the test playbook**

Write this exact file:

```yaml
---
- name: Regression test for MMS unified stack integration
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    repo_root: "{{ playbook_dir }}/.."

  tasks:
    - name: Read Docker Compose template
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/football_club_stack/templates/docker-compose.yml.j2"
      register: compose_template

    - name: Read environment template
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/football_club_stack/templates/env.j2"
      register: env_template

    - name: Read stack defaults
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/football_club_stack/defaults/main.yml"
      register: stack_defaults

    - name: Read subdomain Caddy template
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/caddy/templates/Caddyfile-subdomain.j2"
      register: caddy_subdomain_template

    - name: Read local Caddy template
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/caddy/templates/Caddyfile-local.j2"
      register: caddy_local_template

    - name: Read validation playbook
      ansible.builtin.slurp:
        src: "{{ repo_root }}/playbooks/validate.yml"
      register: validate_playbook

    - name: Read backup script template
      ansible.builtin.slurp:
        src: "{{ repo_root }}/roles/backup/templates/backup.sh.j2"
      register: backup_template

    - name: Read local VM inventory vars
      ansible.builtin.slurp:
        src: "{{ repo_root }}/inventories/local_vm/group_vars/local_vm/vars.yml"
      register: local_vm_vars

    - name: Read production inventory vars
      ansible.builtin.slurp:
        src: "{{ repo_root }}/inventories/production/group_vars/production/vars.yml"
      register: production_vars

    - name: Read local VM vault example
      ansible.builtin.slurp:
        src: "{{ repo_root }}/inventories/local_vm/group_vars/local_vm/vault.example.yml"
      register: local_vm_vault_example

    - name: Read production vault example
      ansible.builtin.slurp:
        src: "{{ repo_root }}/inventories/production/group_vars/production/vault.example.yml"
      register: production_vault_example

    - name: Assert MMS services are in the unified Compose template
      ansible.builtin.assert:
        that:
          - "'mms-postgres:' in (compose_template.content | b64decode)"
          - "'mms-web:' in (compose_template.content | b64decode)"
          - "'mms-qcluster:' in (compose_template.content | b64decode)"
          - "'mms_pgdata:' in (compose_template.content | b64decode)"
          - "'127.0.0.1:8000:8000' in (compose_template.content | b64decode)"
          - "'football_club_stack_mms_image' in (compose_template.content | b64decode)"
          - "'football_club_stack_mms_image_tag' in (compose_template.content | b64decode)"
          - "'DATABASE_URL: ${MMS_DATABASE_URL}' in (compose_template.content | b64decode)"
          - "'DOCUSEAL_API_URL: ${MMS_DOCUSEAL_API_URL}' in (compose_template.content | b64decode)"
          - "'INVOICE_NINJA_API_URL: ${MMS_INVOICE_NINJA_API_URL}' in (compose_template.content | b64decode)"

    - name: Assert MMS environment is rendered from Ansible and Vault values
      ansible.builtin.assert:
        that:
          - "'MMS_DATABASE_URL=postgres://' in (env_template.content | b64decode)"
          - "'mms-postgres:5432' in (env_template.content | b64decode)"
          - "'vault_mms_postgres_password' in (env_template.content | b64decode)"
          - "'MMS_DJANGO_SECRET_KEY=' in (env_template.content | b64decode)"
          - "'vault_mms_django_secret_key' in (env_template.content | b64decode)"
          - "'MMS_SITE_URL=' in (env_template.content | b64decode)"
          - "'football_club_stack_mms_site_url' in (env_template.content | b64decode)"
          - "'MMS_DJANGO_ALLOWED_HOSTS=' in (env_template.content | b64decode)"
          - "'football_club_stack_mms_allowed_hosts' in (env_template.content | b64decode)"
          - "'MMS_AGREEMENT_PROVIDER_MODE=docuseal' in (env_template.content | b64decode)"
          - "'MMS_INVOICE_PROVIDER_MODE=invoiceninja' in (env_template.content | b64decode)"
          - "'MMS_DOCUSEAL_API_URL=' in (env_template.content | b64decode)"
          - "'football_club_stack_mms_docuseal_api_url' in (env_template.content | b64decode)"
          - "'MMS_INVOICE_NINJA_API_URL=' in (env_template.content | b64decode)"
          - "'football_club_stack_mms_invoice_ninja_api_url' in (env_template.content | b64decode)"
          - "'football_club_stack_mms_docuseal_api_url: \"http://docuseal:3000\"' in (stack_defaults.content | b64decode)"
          - "'football_club_stack_mms_invoice_ninja_api_url: \"http://nginx\"' in (stack_defaults.content | b64decode)"

    - name: Assert MMS Caddy routes are managed in the imported snippet
      ansible.builtin.assert:
        that:
          - "'members.' in (caddy_subdomain_template.content | b64decode)"
          - "'football_club_domain' in (caddy_subdomain_template.content | b64decode)"
          - "'reverse_proxy 127.0.0.1:8000' in (caddy_subdomain_template.content | b64decode)"
          - "'members.lan' in (caddy_local_template.content | b64decode)"
          - "'tls internal' in (caddy_local_template.content | b64decode)"
          - "'reverse_proxy 127.0.0.1:8000' in (caddy_local_template.content | b64decode)"

    - name: Assert MMS validation endpoint is checked
      ansible.builtin.assert:
        that:
          - "'members_endpoint' in (validate_playbook.content | b64decode)"
          - "'https://members.lan/healthz' in (validate_playbook.content | b64decode)"
          - "'https://members.' in (validate_playbook.content | b64decode)"
          - "'Check MMS HTTP endpoint' in (validate_playbook.content | b64decode)"

    - name: Assert MMS backup data is covered
      ansible.builtin.assert:
        that:
          - "'mms-postgres' in (backup_template.content | b64decode)"
          - "'mms.sql' in (backup_template.content | b64decode)"
          - "'mms_uploads.tar.gz' in (backup_template.content | b64decode)"
          - "'mms_private_uploads.tar.gz' in (backup_template.content | b64decode)"

    - name: Assert MMS image tags are inventory-specific
      ansible.builtin.assert:
        that:
          - "'football_club_stack_mms_image_tag: \"dev\"' in (local_vm_vars.content | b64decode)"
          - "'football_club_stack_mms_image_tag: \"main\"' in (production_vars.content | b64decode)"

    - name: Assert MMS Vault placeholders exist in both example inventories
      ansible.builtin.assert:
        that:
          - "'vault_mms_django_secret_key' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_postgres_password' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_ocr_encryption_key' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_api_key' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_template_id' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_webhook_secret' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_invoice_ninja_api_key' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_email_host_password' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_superuser_password' in (local_vm_vault_example.content | b64decode)"
          - "'vault_mms_django_secret_key' in (production_vault_example.content | b64decode)"
          - "'vault_mms_postgres_password' in (production_vault_example.content | b64decode)"
          - "'vault_mms_ocr_encryption_key' in (production_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_api_key' in (production_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_template_id' in (production_vault_example.content | b64decode)"
          - "'vault_mms_docuseal_webhook_secret' in (production_vault_example.content | b64decode)"
          - "'vault_mms_invoice_ninja_api_key' in (production_vault_example.content | b64decode)"
          - "'vault_mms_email_host_password' in (production_vault_example.content | b64decode)"
          - "'vault_mms_superuser_password' in (production_vault_example.content | b64decode)"
```

- [ ] **Step 2: Run the new test to verify red phase**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: FAIL. The first failure should mention missing MMS services or missing MMS env keys.

- [ ] **Step 3: Commit the failing test**

```bash
git add ansible/tests/mms_unified_stack.yml
git commit -m "test: cover MMS unified stack integration"
```

## Task 2: Add MMS Compose services and rendered env

**Files:**
- Modify: `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`
- Modify: `ansible/roles/football_club_stack/templates/env.j2`
- Modify: `ansible/roles/football_club_stack/defaults/main.yml`
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`
- Modify: `ansible/inventories/production/group_vars/production/vars.yml`
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`
- Modify: `ansible/inventories/production/group_vars/production/vault.example.yml`

- [ ] **Step 1: Add MMS defaults**

Replace `ansible/roles/football_club_stack/defaults/main.yml` with:

```yaml
---
football_club_stack_invoiceninja_app_url: >-
  {{ 'http://billing.lan' if football_club_caddy_mode == 'local' else 'https://billing.' ~ football_club_domain }}
football_club_stack_mms_image: "codeberg.org/linards-kalvans/fk-cesis-mms"
football_club_stack_mms_image_tag: "main"
football_club_stack_mms_db_name: "fkmms"
football_club_stack_mms_db_user: "fkmms"
football_club_stack_mms_site_url: >-
  {{ 'https://members.lan' if football_club_caddy_mode == 'local' else 'https://members.' ~ football_club_domain }}
football_club_stack_mms_allowed_hosts: >-
  {{ 'members.lan' if football_club_caddy_mode == 'local' else 'members.' ~ football_club_domain }}
football_club_stack_mms_docuseal_api_url: "http://docuseal:3000"
football_club_stack_mms_invoice_ninja_api_url: "http://nginx"
football_club_stack_mms_invoice_ninja_number_prefix: "MMS"
football_club_stack_mms_billing_autosend_enabled: "false"
football_club_stack_mms_billing_send_due_hour: "4"
football_club_stack_mms_billing_payment_sync_hour: "3"
football_club_stack_mms_ocr_provider_mode: "stub"
football_club_stack_mms_tiny_idp_api_url: ""
football_club_stack_mms_email_backend: "django.core.mail.backends.smtp.EmailBackend"
football_club_stack_mms_email_host: "smtp.example.lv"
football_club_stack_mms_email_port: "587"
football_club_stack_mms_email_use_tls: "true"
football_club_stack_mms_email_host_user: ""
football_club_stack_mms_default_from_email: >-
  {{ 'noreply@' ~ football_club_domain }}
football_club_stack_mms_superuser_email: ""
football_club_stack_mms_superuser_username: ""
football_club_stack_mms_audit_retention_days: "730"
football_club_stack_mms_audit_prune_hour: "2"
```

- [ ] **Step 2: Set inventory image tags**

Append this line to `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`:

```yaml
football_club_stack_mms_image_tag: "dev"
```

Append this line to `ansible/inventories/production/group_vars/production/vars.yml`:

```yaml
football_club_stack_mms_image_tag: "main"
```

- [ ] **Step 3: Extend environment template**

Append to `ansible/roles/football_club_stack/templates/env.j2` after `ADMIN_EMAIL={{ football_club_admin_email }}`:

```jinja2

MMS_POSTGRES_DB={{ football_club_stack_mms_db_name }}
MMS_POSTGRES_USER={{ football_club_stack_mms_db_user }}
MMS_POSTGRES_PASSWORD={{ vault_mms_postgres_password }}
MMS_DATABASE_URL=postgres://{{ football_club_stack_mms_db_user }}:{{ vault_mms_postgres_password }}@mms-postgres:5432/{{ football_club_stack_mms_db_name }}
MMS_DJANGO_SECRET_KEY={{ vault_mms_django_secret_key }}
MMS_DJANGO_DEBUG=false
MMS_SITE_URL={{ football_club_stack_mms_site_url }}
MMS_DJANGO_ALLOWED_HOSTS={{ football_club_stack_mms_allowed_hosts }}
MMS_TIME_ZONE={{ football_club_timezone }}
MMS_OCR_PROVIDER_MODE={{ football_club_stack_mms_ocr_provider_mode }}
MMS_TINY_IDP_API_URL={{ football_club_stack_mms_tiny_idp_api_url }}
MMS_TINY_IDP_API_KEY={{ vault_mms_tiny_idp_api_key }}
MMS_OCR_ENCRYPTION_KEY={{ vault_mms_ocr_encryption_key }}
MMS_AGREEMENT_PROVIDER_MODE=docuseal
MMS_DOCUSEAL_API_URL={{ football_club_stack_mms_docuseal_api_url }}
MMS_DOCUSEAL_API_KEY={{ vault_mms_docuseal_api_key }}
MMS_DOCUSEAL_TEMPLATE_ID={{ vault_mms_docuseal_template_id }}
MMS_DOCUSEAL_WEBHOOK_SECRET={{ vault_mms_docuseal_webhook_secret }}
MMS_INVOICE_PROVIDER_MODE=invoiceninja
MMS_INVOICE_NINJA_API_URL={{ football_club_stack_mms_invoice_ninja_api_url }}
MMS_INVOICE_NINJA_API_KEY={{ vault_mms_invoice_ninja_api_key }}
MMS_INVOICE_NINJA_NUMBER_PREFIX={{ football_club_stack_mms_invoice_ninja_number_prefix }}
MMS_BILLING_AUTOSEND_ENABLED={{ football_club_stack_mms_billing_autosend_enabled }}
MMS_BILLING_SEND_DUE_HOUR={{ football_club_stack_mms_billing_send_due_hour }}
MMS_BILLING_PAYMENT_SYNC_HOUR={{ football_club_stack_mms_billing_payment_sync_hour }}
MMS_EMAIL_BACKEND={{ football_club_stack_mms_email_backend }}
MMS_EMAIL_HOST={{ football_club_stack_mms_email_host }}
MMS_EMAIL_PORT={{ football_club_stack_mms_email_port }}
MMS_EMAIL_USE_TLS={{ football_club_stack_mms_email_use_tls }}
MMS_EMAIL_HOST_USER={{ football_club_stack_mms_email_host_user }}
MMS_EMAIL_HOST_PASSWORD={{ vault_mms_email_host_password }}
MMS_DEFAULT_FROM_EMAIL={{ football_club_stack_mms_default_from_email }}
MMS_DJANGO_SUPERUSER_EMAIL={{ football_club_stack_mms_superuser_email }}
MMS_DJANGO_SUPERUSER_USERNAME={{ football_club_stack_mms_superuser_username }}
MMS_DJANGO_SUPERUSER_PASSWORD={{ vault_mms_superuser_password }}
MMS_AUDIT_RETENTION_DAYS={{ football_club_stack_mms_audit_retention_days }}
MMS_AUDIT_PRUNE_HOUR={{ football_club_stack_mms_audit_prune_hour }}
```

- [ ] **Step 4: Add MMS Compose services**

In `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`, insert this block after the `docuseal` service block and before `volumes:`:

```yaml

  mms-postgres:
    image: postgres:18-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${MMS_POSTGRES_DB}
      POSTGRES_USER: ${MMS_POSTGRES_USER}
      POSTGRES_PASSWORD: ${MMS_POSTGRES_PASSWORD}
    volumes:
      - mms_pgdata:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${MMS_POSTGRES_USER} -d ${MMS_POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  mms-web:
    image: {{ football_club_stack_mms_image }}:{{ football_club_stack_mms_image_tag }}
    restart: unless-stopped
    depends_on:
      mms-postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: ${MMS_DATABASE_URL}
      DJANGO_SECRET_KEY: ${MMS_DJANGO_SECRET_KEY}
      DJANGO_DEBUG: ${MMS_DJANGO_DEBUG}
      SITE_URL: ${MMS_SITE_URL}
      DJANGO_ALLOWED_HOSTS: ${MMS_DJANGO_ALLOWED_HOSTS}
      TIME_ZONE: ${MMS_TIME_ZONE}
      OCR_PROVIDER_MODE: ${MMS_OCR_PROVIDER_MODE}
      TINY_IDP_API_URL: ${MMS_TINY_IDP_API_URL}
      TINY_IDP_API_KEY: ${MMS_TINY_IDP_API_KEY}
      OCR_ENCRYPTION_KEY: ${MMS_OCR_ENCRYPTION_KEY}
      AGREEMENT_PROVIDER_MODE: ${MMS_AGREEMENT_PROVIDER_MODE}
      DOCUSEAL_API_URL: ${MMS_DOCUSEAL_API_URL}
      DOCUSEAL_API_KEY: ${MMS_DOCUSEAL_API_KEY}
      DOCUSEAL_TEMPLATE_ID: ${MMS_DOCUSEAL_TEMPLATE_ID}
      DOCUSEAL_WEBHOOK_SECRET: ${MMS_DOCUSEAL_WEBHOOK_SECRET}
      INVOICE_PROVIDER_MODE: ${MMS_INVOICE_PROVIDER_MODE}
      INVOICE_NINJA_API_URL: ${MMS_INVOICE_NINJA_API_URL}
      INVOICE_NINJA_API_KEY: ${MMS_INVOICE_NINJA_API_KEY}
      INVOICE_NINJA_NUMBER_PREFIX: ${MMS_INVOICE_NINJA_NUMBER_PREFIX}
      BILLING_AUTOSEND_ENABLED: ${MMS_BILLING_AUTOSEND_ENABLED}
      BILLING_SEND_DUE_HOUR: ${MMS_BILLING_SEND_DUE_HOUR}
      BILLING_PAYMENT_SYNC_HOUR: ${MMS_BILLING_PAYMENT_SYNC_HOUR}
      EMAIL_BACKEND: ${MMS_EMAIL_BACKEND}
      EMAIL_HOST: ${MMS_EMAIL_HOST}
      EMAIL_PORT: ${MMS_EMAIL_PORT}
      EMAIL_USE_TLS: ${MMS_EMAIL_USE_TLS}
      EMAIL_HOST_USER: ${MMS_EMAIL_HOST_USER}
      EMAIL_HOST_PASSWORD: ${MMS_EMAIL_HOST_PASSWORD}
      DEFAULT_FROM_EMAIL: ${MMS_DEFAULT_FROM_EMAIL}
      DJANGO_SUPERUSER_EMAIL: ${MMS_DJANGO_SUPERUSER_EMAIL}
      DJANGO_SUPERUSER_USERNAME: ${MMS_DJANGO_SUPERUSER_USERNAME}
      DJANGO_SUPERUSER_PASSWORD: ${MMS_DJANGO_SUPERUSER_PASSWORD}
      AUDIT_RETENTION_DAYS: ${MMS_AUDIT_RETENTION_DAYS}
      AUDIT_PRUNE_HOUR: ${MMS_AUDIT_PRUNE_HOUR}
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - mms_uploads:/app/uploads
      - mms_private_uploads:/app/private-uploads
    command:
      - sh
      - -c
      - >
        python manage.py migrate --noinput &&
        exec gunicorn fk_cesis_mms.wsgi:application
        --bind 0.0.0.0:8000
        --workers 3
        --access-logfile -
        --error-logfile -

  mms-qcluster:
    image: {{ football_club_stack_mms_image }}:{{ football_club_stack_mms_image_tag }}
    restart: unless-stopped
    depends_on:
      mms-web:
        condition: service_started
    environment:
      DATABASE_URL: ${MMS_DATABASE_URL}
      DJANGO_SECRET_KEY: ${MMS_DJANGO_SECRET_KEY}
      DJANGO_DEBUG: ${MMS_DJANGO_DEBUG}
      SITE_URL: ${MMS_SITE_URL}
      DJANGO_ALLOWED_HOSTS: ${MMS_DJANGO_ALLOWED_HOSTS}
      TIME_ZONE: ${MMS_TIME_ZONE}
      OCR_PROVIDER_MODE: ${MMS_OCR_PROVIDER_MODE}
      TINY_IDP_API_URL: ${MMS_TINY_IDP_API_URL}
      TINY_IDP_API_KEY: ${MMS_TINY_IDP_API_KEY}
      OCR_ENCRYPTION_KEY: ${MMS_OCR_ENCRYPTION_KEY}
      AGREEMENT_PROVIDER_MODE: ${MMS_AGREEMENT_PROVIDER_MODE}
      DOCUSEAL_API_URL: ${MMS_DOCUSEAL_API_URL}
      DOCUSEAL_API_KEY: ${MMS_DOCUSEAL_API_KEY}
      DOCUSEAL_TEMPLATE_ID: ${MMS_DOCUSEAL_TEMPLATE_ID}
      DOCUSEAL_WEBHOOK_SECRET: ${MMS_DOCUSEAL_WEBHOOK_SECRET}
      INVOICE_PROVIDER_MODE: ${MMS_INVOICE_PROVIDER_MODE}
      INVOICE_NINJA_API_URL: ${MMS_INVOICE_NINJA_API_URL}
      INVOICE_NINJA_API_KEY: ${MMS_INVOICE_NINJA_API_KEY}
      INVOICE_NINJA_NUMBER_PREFIX: ${MMS_INVOICE_NINJA_NUMBER_PREFIX}
      BILLING_AUTOSEND_ENABLED: ${MMS_BILLING_AUTOSEND_ENABLED}
      BILLING_SEND_DUE_HOUR: ${MMS_BILLING_SEND_DUE_HOUR}
      BILLING_PAYMENT_SYNC_HOUR: ${MMS_BILLING_PAYMENT_SYNC_HOUR}
      EMAIL_BACKEND: ${MMS_EMAIL_BACKEND}
      EMAIL_HOST: ${MMS_EMAIL_HOST}
      EMAIL_PORT: ${MMS_EMAIL_PORT}
      EMAIL_USE_TLS: ${MMS_EMAIL_USE_TLS}
      EMAIL_HOST_USER: ${MMS_EMAIL_HOST_USER}
      EMAIL_HOST_PASSWORD: ${MMS_EMAIL_HOST_PASSWORD}
      DEFAULT_FROM_EMAIL: ${MMS_DEFAULT_FROM_EMAIL}
      DJANGO_SUPERUSER_EMAIL: ${MMS_DJANGO_SUPERUSER_EMAIL}
      DJANGO_SUPERUSER_USERNAME: ${MMS_DJANGO_SUPERUSER_USERNAME}
      DJANGO_SUPERUSER_PASSWORD: ${MMS_DJANGO_SUPERUSER_PASSWORD}
      AUDIT_RETENTION_DAYS: ${MMS_AUDIT_RETENTION_DAYS}
      AUDIT_PRUNE_HOUR: ${MMS_AUDIT_PRUNE_HOUR}
    volumes:
      - mms_uploads:/app/uploads
      - mms_private_uploads:/app/private-uploads
    command: ["python", "manage.py", "qcluster"]
```

Add the new volumes under the existing `volumes:` list:

```yaml
  mms_pgdata:
  mms_uploads:
  mms_private_uploads:
```

- [ ] **Step 5: Add MMS Vault placeholders**

Append to `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml` and `ansible/inventories/production/group_vars/production/vault.example.yml`:

```yaml
vault_mms_django_secret_key: "change-me"
vault_mms_postgres_password: "change-me"
vault_mms_tiny_idp_api_key: ""
vault_mms_ocr_encryption_key: "change-me-fernet-key"
vault_mms_docuseal_api_key: "change-me"
vault_mms_docuseal_template_id: "change-me"
vault_mms_docuseal_webhook_secret: "change-me"
vault_mms_invoice_ninja_api_key: "change-me"
vault_mms_email_host_password: "change-me"
vault_mms_superuser_password: "change-me"
```

- [ ] **Step 6: Run the MMS regression test**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: FAIL only on Caddy route, validation, or backup assertions that Task 3 and Task 4 will implement. All Compose/env/inventory/vault assertions should PASS.

- [ ] **Step 7: Commit Compose/env changes**

```bash
git add ansible/roles/football_club_stack/templates/docker-compose.yml.j2 \
  ansible/roles/football_club_stack/templates/env.j2 \
  ansible/roles/football_club_stack/defaults/main.yml \
  ansible/inventories/local_vm/group_vars/local_vm/vars.yml \
  ansible/inventories/production/group_vars/production/vars.yml \
  ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml \
  ansible/inventories/production/group_vars/production/vault.example.yml
git commit -m "feat(ansible): add MMS stack services"
```

## Task 3: Add MMS Caddy route and validation

**Files:**
- Modify: `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
- Modify: `ansible/roles/caddy/templates/Caddyfile-local.j2`
- Modify: `ansible/playbooks/validate.yml`

- [ ] **Step 1: Add subdomain Caddy route**

Append to `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`:

```caddyfile

members.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:8000
}
```

- [ ] **Step 2: Add local Caddy route**

Append to `ansible/roles/caddy/templates/Caddyfile-local.j2`:

```caddyfile

members.lan {
  tls internal
  reverse_proxy 127.0.0.1:8000
}
```

- [ ] **Step 3: Add members endpoint fact**

In `ansible/playbooks/validate.yml`, in task `Set service endpoint URLs`, add this key after `agreements_endpoint`:

```yaml
        members_endpoint: >-
          {{ 'https://members.lan/healthz' if football_club_caddy_mode == 'local'
             else 'https://members.' ~ football_club_domain ~ '/healthz' }}
```

- [ ] **Step 4: Add MMS HTTP validation task**

Append after `Check Docuseal HTTP endpoint` in `ansible/playbooks/validate.yml`:

```yaml

    - name: Check MMS HTTP endpoint
      ansible.builtin.uri:
        url: "{{ members_endpoint }}"
        method: GET
        validate_certs: "{{ football_club_caddy_mode != 'local' }}"
        status_code:
          - 200
        return_content: false
```

- [ ] **Step 5: Run the MMS regression test**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: FAIL only on backup assertions from Task 4. Caddy and validation assertions should PASS.

- [ ] **Step 6: Commit routing/validation changes**

```bash
git add ansible/roles/caddy/templates/Caddyfile-subdomain.j2 \
  ansible/roles/caddy/templates/Caddyfile-local.j2 \
  ansible/playbooks/validate.yml
git commit -m "feat(ansible): route and validate MMS"
```

## Task 4: Add MMS backup coverage

**Files:**
- Modify: `ansible/roles/backup/templates/backup.sh.j2`

- [ ] **Step 1: Add MMS database dump and upload archives**

In `ansible/roles/backup/templates/backup.sh.j2`, insert after the Docuseal tar command and before `rsync -az`:

```bash

${COMPOSE} exec -T mms-postgres sh -c 'pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}"' > "${BACKUP_DIR}/mms.sql"

docker run --rm -v {{ football_club_compose_project_name }}_mms_uploads:/data:ro -v "${BACKUP_DIR}":/backup alpine \
  tar czf /backup/mms_uploads.tar.gz -C /data .

docker run --rm -v {{ football_club_compose_project_name }}_mms_private_uploads:/data:ro -v "${BACKUP_DIR}":/backup alpine \
  tar czf /backup/mms_private_uploads.tar.gz -C /data .
```

- [ ] **Step 2: Run the MMS regression test**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: PASS.

- [ ] **Step 3: Commit backup changes**

```bash
git add ansible/roles/backup/templates/backup.sh.j2
git commit -m "feat(ansible): back up MMS data"
```

## Task 5: Update source-of-truth documentation

**Files:**
- Modify: `ansible/README.md`
- Modify: `docs/fk-cesis-mms-deployment.md`
- Modify: `docs/implementation-plan.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update Ansible README active stack text**

In `ansible/README.md`, change line 3 from:

```markdown
This directory deploys the current FK CĒSIS environment foundation: InvoiceNinja, Docuseal, Caddy, and backup automation.
```

to:

```markdown
This directory deploys the current FK CĒSIS environment foundation: InvoiceNinja, Docuseal, FK Cēsis MMS, Caddy, and backup automation.
```

- [ ] **Step 2: Add members DNS row**

In `ansible/README.md`, add this row to the DNS table after `agreements.<domain>`:

```markdown
| `members.<domain>` | FK Cēsis MMS |
```

Add this example DNS line after `agreements.example.lv -> 192.0.2.10`:

```text
members.example.lv    -> 192.0.2.10
```

- [ ] **Step 3: Add members local hosts entry**

In the local `/etc/hosts` example, change:

```bash
192.168.x.x billing.lan agreements.lan
```

to:

```bash
192.168.x.x billing.lan agreements.lan members.lan
```

- [ ] **Step 4: Update Ansible README validation expectations**

In `ansible/README.md`, add this bullet after `Docuseal endpoint (`agreements`)`:

```markdown
- FK Cēsis MMS endpoint (`members`)
```

Change:

```markdown
- backup workflow covers active persistent data only
```

to:

```markdown
- backup workflow covers active persistent data for InvoiceNinja, Docuseal, and MMS
```

- [ ] **Step 5: Replace MMS deployment doc with legacy pointer**

Replace `docs/fk-cesis-mms-deployment.md` with:

```markdown
# FK Cēsis MMS Deployment

## Current source of truth

FK Cēsis MMS is deployed by the unified Ansible stack in `ansible/`.

The active runtime is part of the same Docker Compose project as InvoiceNinja and Docuseal so MMS can call them over the internal Docker network:

- InvoiceNinja: `http://nginx`
- Docuseal: `http://docuseal:3000`

Ingress is handled by Caddy:

- Production-style: `https://members.<domain>`
- Local VM: `https://members.lan`

Use `ansible/README.md` for operator setup, secrets, validation, and backup workflow.

## Legacy manual runtime

The standalone files under `deploy/fk-cesis-mms/` are retained only as legacy/manual reference material. They are not the primary deployment path for this repository.

Do not deploy new FK Cēsis MMS environments from `/opt/fk-cesis-mms` unless a future approved spec restores that mode.

## Secrets rule

Never commit real `.env` values, deploy webhook secrets, API keys, SMTP passwords, OCR keys, Docuseal keys, InvoiceNinja keys, database passwords, or Django secrets.
```

- [ ] **Step 6: Update implementation plan active scope**

In `docs/implementation-plan.md`, update the active scope list to include:

```markdown
- FK Cēsis MMS for member management deployment integration
```

Update the managed runtime table to include:

```markdown
| **FK Cēsis MMS** | Member management deployment integration | `codeberg.org/linards-kalvans/fk-cesis-mms:<tag>` |
```

Update route lists to include:

```markdown
- `members.<domain>` → FK Cēsis MMS
```

and:

```markdown
- `members.lan` → FK Cēsis MMS
```

Update backup scope to include:

```markdown
- FK Cēsis MMS database dump
- FK Cēsis MMS uploads and private uploads volumes
```

- [ ] **Step 7: Update AGENTS.md active scope**

In `AGENTS.md`, update scope and tech stack references so active deployment scope includes FK Cēsis MMS. Required concrete changes:

Change:

```markdown
- Maintain repeatable Ansible deployment for InvoiceNinja, Docuseal, Caddy, and backup automation.
```

to:

```markdown
- Maintain repeatable Ansible deployment for InvoiceNinja, Docuseal, FK Cēsis MMS, Caddy, and backup automation.
```

Change:

```markdown
- Milestone 2: keep local VM and production-style deployment repeatable for InvoiceNinja, Docuseal, Caddy, and backups.
```

to:

```markdown
- Milestone 2: keep local VM and production-style deployment repeatable for InvoiceNinja, Docuseal, FK Cēsis MMS, Caddy, and backups.
```

Change:

```markdown
- Preserve room to add the future in-house member management system later, but do not define or implement it in this repo yet.
```

to:

```markdown
- Keep FK Cēsis MMS deployment integrated in the active Ansible stack; application development remains in the separate MMS project.
```

Add this tech stack bullet near Docuseal:

```markdown
- FK Cēsis MMS: `codeberg.org/linards-kalvans/fk-cesis-mms:<tag>` with PostgreSQL.
```

- [ ] **Step 8: Run docs-related regression test**

Run:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: PASS.

- [ ] **Step 9: Commit docs changes**

```bash
git add ansible/README.md docs/fk-cesis-mms-deployment.md docs/implementation-plan.md AGENTS.md
git commit -m "docs: document MMS unified deployment"
```

## Task 6: Run full required verification

**Files:**
- No file changes expected.

- [ ] **Step 1: Run MMS regression test**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/mms_unified_stack.yml
```

Expected: PASS.

- [ ] **Step 2: Run existing Caddy regression test**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/caddy_import_snippet.yml
```

Expected: PASS.

- [ ] **Step 3: Run ansible-lint**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-lint ansible/playbooks/site.yml ansible/playbooks/validate.yml ansible/tests/mms_unified_stack.yml ansible/tests/caddy_import_snippet.yml
```

Expected: PASS.

- [ ] **Step 4: Run yamllint**

```bash
yamllint .
```

Expected: PASS.

- [ ] **Step 5: Run site syntax check**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
```

Expected: PASS.

- [ ] **Step 6: Run validate syntax check**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
```

Expected: PASS.

- [ ] **Step 7: Run check/diff dry run if vault is available**

Run only if the user provides the local VM vault password or a usable test vault:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff ansible/playbooks/site.yml --ask-vault-pass
```

Expected: PASS.

If vault password is not available in the agent session, report this as a blocked external verification step, not as completed.

- [ ] **Step 8: Apply to local VM if access and vault are available**

Run only if the user confirms the local VM is reachable and provides the needed vault password:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/site.yml --ask-vault-pass
```

Expected: PASS.

- [ ] **Step 9: Validate local VM if access and vault are available**

Run only after Step 8 succeeds:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/validate.yml --ask-vault-pass
```

Expected: PASS.

- [ ] **Step 10: Final commit if verification caused any edits**

If verification required fixes, commit only those fixes:

```bash
git status --short
git add <changed-files>
git commit -m "fix(ansible): satisfy MMS deployment checks"
```

Expected: clean working tree after commit.

## Implementation handoff notes

- Use task-level `become` only. Do not add play-level `become`.
- Do not edit `ansible/inventories/local_vm/group_vars/local_vm/vault.yml`; it may contain encrypted local secrets.
- Do not commit plaintext secrets.
- Do not remove standalone `deploy/fk-cesis-mms/` files in this implementation; docs mark them legacy/manual only.
- Do not regenerate `docs/html/implementation-plan.html`.
- Keep changes scoped to MMS integration only; do not reintroduce Dolibarr, n8n, or DocTR.
