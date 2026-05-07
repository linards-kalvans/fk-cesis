# Caddy Routing Modes Implementation Plan

> Historical-only note for current repo work: this entire document is retained only for repo history and is not current guidance, including its routing-mode decisions. Use `docs/implementation-plan.md` as the active owner for current repo work, narrowed by `docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable path-based reverse proxy routing under a single Tailscale domain for local VM testing, while preserving subdomain routing for production, controlled entirely by Ansible inventory variables.

**Architecture:** Two Caddyfile templates (subdomain vs path) selected dynamically by the caddy role. Service URLs (Dolibarr, InvoiceNinja, n8n) are computed as derived Ansible variables based on `football_club_caddy_mode`, rendered into the Docker Compose template. Validation playbook constructs smoke-test URLs per mode.

**Tech Stack:** Ansible, Jinja2, Caddy, Docker Compose

---

## File Structure

| File | Action | Purpose |
|---|---|---|
| `ansible/roles/football_club_stack/defaults/main.yml` | Create | Derived URL variables computed from `football_club_caddy_mode` and `football_club_domain` |
| `ansible/roles/caddy/templates/Caddyfile-subdomain.j2` | Create | Subdomain-based routing template (replaces existing Caddyfile.j2) |
| `ansible/roles/caddy/templates/Caddyfile-path.j2` | Create | Path-based routing template for single-domain Tailscale access |
| `ansible/roles/caddy/templates/Caddyfile.j2` | Delete | Old template, superseded by mode-specific templates |
| `ansible/roles/football_club_stack/templates/docker-compose.yml.j2` | Modify | Use derived URL variables instead of hardcoded subdomain URLs |
| `ansible/inventories/local_vm/group_vars/local_vm/vars.yml` | Modify | Add `football_club_caddy_mode`, port vars, set domain to Tailscale hostname |
| `ansible/inventories/production/group_vars/production/vars.yml` | Modify | Add `football_club_caddy_mode`, port vars, keep production domain |
| `ansible/roles/caddy/tasks/main.yml` | Modify | Select template source dynamically via `football_club_caddy_mode` |
| `ansible/playbooks/validate.yml` | Modify | Construct service URLs conditionally based on routing mode |

---

### Task 1: Create Derived URL Variables

**Files:**
- Create: `ansible/roles/football_club_stack/defaults/main.yml`

- [ ] **Step 1: Write the defaults file**

Create `ansible/roles/football_club_stack/defaults/main.yml`:

```yaml
---
dolibarr_url_root: >-
  {{ 'https://' ~ football_club_domain ~ '/club'
     if football_club_caddy_mode == 'path'
     else 'https://club.' ~ football_club_domain }}

invoiceninja_app_url: >-
  {{ 'https://' ~ football_club_domain ~ '/billing'
     if football_club_caddy_mode == 'path'
     else 'https://billing.' ~ football_club_domain }}

n8n_host: >-
  {{ football_club_domain
     if football_club_caddy_mode == 'path'
     else 'n8n.' ~ football_club_domain }}

n8n_webhook_url: >-
  {{ 'https://' ~ football_club_domain ~ '/n8n/'
     if football_club_caddy_mode == 'path'
     else 'https://n8n.' ~ football_club_domain ~ '/' }}
```

- [ ] **Step 2: Verify Jinja2 syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('ansible/roles/football_club_stack/defaults/main.yml'))"`
Expected: No output (success, no exception)

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/football_club_stack/defaults/main.yml
git commit -m "feat(ansible): add derived URL variables for routing modes"
```

---

### Task 2: Create Subdomain Caddyfile Template

**Files:**
- Create: `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
- Delete: `ansible/roles/caddy/templates/Caddyfile.j2`

- [ ] **Step 1: Create the subdomain template**

Create `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`:

```
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
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

- [ ] **Step 2: Remove old template**

```bash
git rm ansible/roles/caddy/templates/Caddyfile.j2
```

- [ ] **Step 3: Commit**

```bash
git add ansible/roles/caddy/templates/Caddyfile-subdomain.j2
git add ansible/roles/caddy/templates/Caddyfile.j2
git commit -m "feat(caddy): add subdomain Caddyfile template, remove old unified template"
```

---

### Task 3: Create Path-Based Caddyfile Template

**Files:**
- Create: `ansible/roles/caddy/templates/Caddyfile-path.j2`

- [ ] **Step 1: Create the path template**

Create `ansible/roles/caddy/templates/Caddyfile-path.j2`:

```
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
  email {{ football_club_admin_email }}
}

{{ football_club_domain }} {
  handle_path /club/* {
    reverse_proxy 127.0.0.1:8081
  }

  handle_path /billing/* {
    reverse_proxy 127.0.0.1:8082
  }

  handle_path /n8n/* {
    reverse_proxy 127.0.0.1:5678
  }

  handle_path /agreements/* {
    reverse_proxy 127.0.0.1:3000
  }

  handle {
    redir /club/
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/caddy/templates/Caddyfile-path.j2
git commit -m "feat(caddy): add path-based Caddyfile template for Tailscale routing"
```

---

### Task 4: Update Docker Compose Template

**Files:**
- Modify: `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`

- [ ] **Step 1: Replace hardcoded service URLs with derived variables**

In `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`, make these exact replacements:

Replace line 15:
```
      DOLI_URL_ROOT: https://club.${DOMAIN}
```
with:
```
      DOLI_URL_ROOT: {{ dolibarr_url_root }}
```

Replace line 41:
```
      APP_URL: https://billing.${DOMAIN}
```
with:
```
      APP_URL: {{ invoiceninja_app_url }}
```

Replace line 75:
```
      N8N_HOST: n8n.${DOMAIN}
```
with:
```
      N8N_HOST: {{ n8n_host }}
```

Replace line 77:
```
      WEBHOOK_URL: https://n8n.${DOMAIN}/
```
with:
```
      WEBHOOK_URL: {{ n8n_webhook_url }}
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/football_club_stack/templates/docker-compose.yml.j2
git commit -m "feat(compose): use derived URL variables for service URLs"
```

---

### Task 5: Update Caddy Role to Select Template Dynamically

**Files:**
- Modify: `ansible/roles/caddy/tasks/main.yml`

- [ ] **Step 1: Change template source from static to dynamic**

In `ansible/roles/caddy/tasks/main.yml`, replace lines 36-44:

```yaml
- name: Render managed Caddyfile
  ansible.builtin.template:
    src: Caddyfile.j2
    dest: "{{ football_club_caddyfile_path }}"
    owner: root
    group: root
    mode: "0644"
  become: true
  notify: Reload Caddy
```

with:

```yaml
- name: Render managed Caddyfile
  ansible.builtin.template:
    src: "Caddyfile-{{ football_club_caddy_mode }}.j2"
    dest: "{{ football_club_caddyfile_path }}"
    owner: root
    group: root
    mode: "0644"
  become: true
  notify: Reload Caddy
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/caddy/tasks/main.yml
git commit -m "feat(caddy): select Caddyfile template by routing mode"
```

---

### Task 6: Update Local VM Inventory Variables

**Files:**
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`

- [ ] **Step 1: Add routing mode, ports, and update domain**

In `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`, replace the entire file content with:

```yaml
---
football_club_domain: "skuby7.tail45ce0a.ts.net"
football_club_admin_email: "admin@mplytics.eu"
football_club_project_dir: "/opt/fk-cesis"
football_club_backup_dir: "/opt/backups/fk-cesis"
football_club_backup_remote: "linards@192.168.3.249:/opt/backups/fk-cesis/"
football_club_timezone: "Europe/Riga"
football_club_caddyfile_path: "/etc/caddy/Caddyfile"
football_club_caddy_backup_dir: "/etc/caddy/backups"
football_club_compose_project_name: "fk-cesis"
football_club_doctr_enabled: false
football_club_caddy_mode: "path"
football_club_caddy_http_port: 80
football_club_caddy_https_port: 443
```

- [ ] **Step 2: Commit**

```bash
git add ansible/inventories/local_vm/group_vars/local_vm/vars.yml
git commit -m "feat(inventory): configure local VM for path-based Tailscale routing"
```

---

### Task 7: Update Production Inventory Variables

**Files:**
- Modify: `ansible/inventories/production/group_vars/production/vars.yml`

- [ ] **Step 1: Add routing mode and port variables**

In `ansible/inventories/production/group_vars/production/vars.yml`, replace the entire file content with:

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
football_club_caddy_mode: "subdomain"
football_club_caddy_http_port: 80
football_club_caddy_https_port: 443
```

- [ ] **Step 2: Commit**

```bash
git add ansible/inventories/production/group_vars/production/vars.yml
git commit -m "feat(inventory): add caddy routing mode and port vars for production"
```

---

### Task 8: Update Validation Playbook for Mode-Aware URLs

**Files:**
- Modify: `ansible/playbooks/validate.yml`

- [ ] **Step 1: Replace hardcoded subdomain URLs with computed URLs**

In `ansible/playbooks/validate.yml`, replace lines 32-66 (the four `ansible.builtin.uri` tasks) with:

```yaml
    - name: Set service endpoint URLs
      ansible.builtin.set_fact:
        dolibarr_endpoint: >-
          {{ 'https://' ~ football_club_domain ~ '/club/'
             if football_club_caddy_mode == 'path'
             else 'https://club.' ~ football_club_domain ~ '/' }}
        billing_endpoint: >-
          {{ 'https://' ~ football_club_domain ~ '/billing/'
             if football_club_caddy_mode == 'path'
             else 'https://billing.' ~ football_club_domain ~ '/' }}
        n8n_endpoint: >-
          {{ 'https://' ~ football_club_domain ~ '/n8n/'
             if football_club_caddy_mode == 'path'
             else 'https://n8n.' ~ football_club_domain ~ '/' }}
        agreements_endpoint: >-
          {{ 'https://' ~ football_club_domain ~ '/agreements/'
             if football_club_caddy_mode == 'path'
             else 'https://agreements.' ~ football_club_domain ~ '/' }}

    - name: Check Dolibarr HTTP endpoint
      ansible.builtin.uri:
        url: "{{ dolibarr_endpoint }}"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check InvoiceNinja HTTP endpoint
      ansible.builtin.uri:
        url: "{{ billing_endpoint }}"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check n8n HTTP endpoint
      ansible.builtin.uri:
        url: "{{ n8n_endpoint }}"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false

    - name: Check Docuseal HTTP endpoint
      ansible.builtin.uri:
        url: "{{ agreements_endpoint }}"
        method: GET
        status_code:
          - 200
          - 302
        return_content: false
```

- [ ] **Step 2: Commit**

```bash
git add ansible/playbooks/validate.yml
git commit -m "feat(validate): construct service URLs based on routing mode"
```

---

### Task 9: Run Static Analysis and Syntax Checks

**Files:**
- All modified files

- [ ] **Step 1: Run yamllint**

Run: `cd ansible && yamllint .`
Expected: No errors, no warnings (or only warnings pre-existing before this change)

- [ ] **Step 2: Run ansible-lint**

Run: `cd ansible && ansible-lint`
Expected: Pass with no rule violations for modified files

- [ ] **Step 3: Syntax-check with local_vm inventory**

Run: `cd ansible && ansible-playbook --syntax-check -i inventories/local_vm/hosts.yml playbooks/site.yml`
Expected: `playbook: playbooks/site.yml` with no syntax errors

- [ ] **Step 4: Syntax-check with production inventory**

Run: `cd ansible && ansible-playbook --syntax-check -i inventories/production/hosts.yml playbooks/site.yml`
Expected: `playbook: playbooks/site.yml` with no syntax errors

- [ ] **Step 5: Syntax-check validate playbook (local_vm)**

Run: `cd ansible && ansible-playbook --syntax-check -i inventories/local_vm/hosts.yml playbooks/validate.yml`
Expected: `playbook: playbooks/validate.yml` with no syntax errors

- [ ] **Step 6: Syntax-check validate playbook (production)**

Run: `cd ansible && ansible-playbook --syntax-check -i inventories/production/hosts.yml playbooks/validate.yml`
Expected: `playbook: playbooks/validate.yml` with no syntax errors

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "test(ansible): validate syntax and lint for routing mode changes"
```

---

### Task 10: Verify Template Rendering with Dry-Run

**Files:**
- All templates

- [ ] **Step 1: Dry-run site playbook against local_vm**

Run: `cd ansible && ansible-playbook --check --diff -i inventories/local_vm/hosts.yml playbooks/site.yml`
Expected: Shows changes to `/etc/caddy/Caddyfile` rendered from `Caddyfile-path.j2`, `/opt/fk-cesis/docker-compose.yml` with path-mode URLs, and no unexpected changes elsewhere.

- [ ] **Step 2: Dry-run site playbook against production**

Run: `cd ansible && ansible-playbook --check --diff -i inventories/production/hosts.yml playbooks/site.yml`
Expected: Shows changes to `/etc/caddy/Caddyfile` rendered from `Caddyfile-subdomain.j2`, `/opt/football-club/docker-compose.yml` with subdomain URLs, and no unexpected changes elsewhere.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(ansible): dry-run verification for both inventories"
```

---

### Task 11: Update Implementation Plan Documentation

**Files:**
- Modify: `docs/implementation-plan.md`

- [ ] **Step 1: Update Caddy configuration section**

In `docs/implementation-plan.md`, replace lines 193-215 (the Caddy configuration section and managed Caddyfile block) with:

```markdown
### Caddy configuration

Ansible installs and manages Caddy. If the target host already has a Caddyfile, back it up before replacing it with the managed configuration.

Caddy routing mode is controlled by the `football_club_caddy_mode` inventory variable:

- `subdomain` — each service gets its own subdomain (production default)
- `path` — all services share one domain with path prefixes (local VM / Tailscale)

**Subdomain mode Caddyfile:**

```
club.{$DOMAIN} {
  reverse_proxy dolibarr:80
}

billing.{$DOMAIN} {
  reverse_proxy invoiceninja:80
}

n8n.{$DOMAIN} {
  reverse_proxy n8n:5678
}

agreements.{$DOMAIN} {
  reverse_proxy docuseal:3000
}
```

**Path mode Caddyfile:**

```
{$DOMAIN} {
  handle_path /club/* {
    reverse_proxy dolibarr:80
  }

  handle_path /billing/* {
    reverse_proxy invoiceninja:80
  }

  handle_path /n8n/* {
    reverse_proxy n8n:5678
  }

  handle_path /agreements/* {
    reverse_proxy docuseal:3000
  }

  handle {
    redir /club/
  }
}
```

Service containers receive correctly computed `*_URL` environment variables so self-referential links (emails, redirects, webhooks) match the external access pattern.
```

- [ ] **Step 2: Commit**

```bash
git add docs/implementation-plan.md
git commit -m "docs: update Caddy configuration for routing modes"
```

---

## Self-Review

**1. Spec coverage:**
- [x] Two Caddyfile templates → Task 2, Task 3
- [x] Dynamic template selection → Task 5
- [x] Derived URL variables → Task 1, Task 4
- [x] Inventory variable additions → Task 6, Task 7
- [x] Validation playbook updates → Task 8
- [x] Port configurability → included in Caddyfile templates (new variables)
- [x] Implementation plan doc update → Task 11

**2. Placeholder scan:**
- No "TBD", "TODO", or "implement later" found.
- No vague instructions like "add appropriate error handling".
- All code blocks contain exact replacement text.
- All commands have exact expected output descriptions.

**3. Type consistency:**
- Variable names match across all files: `football_club_caddy_mode`, `football_club_caddy_http_port`, `football_club_caddy_https_port`, `dolibarr_url_root`, `invoiceninja_app_url`, `n8n_host`, `n8n_webhook_url`.
- Template filenames consistently use `Caddyfile-{{ football_club_caddy_mode }}.j2` pattern.

**4. Testability:**
- Every task is a single file change or verification command.
- Static analysis commands are explicit with expected outcomes.
- Dry-run commands verify template rendering without mutating the VM.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-27-caddy-routing-modes.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints

Which approach?
