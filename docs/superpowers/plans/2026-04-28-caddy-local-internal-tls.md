# Caddy Local Internal TLS Implementation Plan

> Historical-only note for current repo work: this entire document is retained only for repo history and is not current guidance, including its local TLS and routing decisions. Use `docs/implementation-plan.md` as the active owner for current repo work, narrowed by `docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace path-based local Caddy mode with `.lan` subdomain mode using Caddy internal TLS, while preserving production subdomain mode.

**Architecture:** Two Caddyfile templates (`Caddyfile-subdomain.j2` for production, `Caddyfile-local.j2` for local VM) selected by `football_club_caddy_mode`. Derived URL variables switch to `.lan` hostnames when mode is `local`.

**Tech Stack:** Ansible, Jinja2, Caddy

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `ansible/roles/caddy/templates/Caddyfile-local.j2` | Create | Local `.lan` subdomain routing with `tls internal` |
| `ansible/roles/caddy/templates/Caddyfile-path.j2` | Delete | Old path-based template (replaced) |
| `ansible/roles/football_club_stack/defaults/main.yml` | Modify | Derived URL variables: `path` → `local` |
| `ansible/inventories/local_vm/group_vars/local_vm/vars.yml` | Modify | `football_club_caddy_mode: "local"` |
| `ansible/playbooks/validate.yml` | Modify | Endpoint facts: `path` → `local` |
| `docs/implementation-plan.md` | Modify | Update Phase 1 Caddy section for local mode |
| `AGENTS.md` | Modify | Remove path mode references if any |

---

### Task 1: Create Local Caddyfile Template

**Files:**
- Create: `ansible/roles/caddy/templates/Caddyfile-local.j2`

- [ ] **Step 1: Create `Caddyfile-local.j2`**

```jinja2
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
}

club.lan {
  tls internal
  reverse_proxy 127.0.0.1:8081
}

billing.lan {
  tls internal
  reverse_proxy 127.0.0.1:8082
}

n8n.lan {
  tls internal
  reverse_proxy 127.0.0.1:5678
}

agreements.lan {
  tls internal
  reverse_proxy 127.0.0.1:3000
}
```

**Verification:** Confirm file exists.
```bash
ls ansible/roles/caddy/templates/Caddyfile-local.j2
```

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/caddy/templates/Caddyfile-local.j2
git commit -m "feat(caddy): add local .lan subdomain template with internal TLS"
```

---

### Task 2: Delete Old Path Template

**Files:**
- Delete: `ansible/roles/caddy/templates/Caddyfile-path.j2`

- [ ] **Step 1: Remove old template**

```bash
rm ansible/roles/caddy/templates/Caddyfile-path.j2
```

**Verification:** Confirm file is gone.
```bash
ls ansible/roles/caddy/templates/
```
Expected: only `Caddyfile-subdomain.j2` and `Caddyfile-local.j2`

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/caddy/templates/Caddyfile-path.j2
git commit -m "refactor(caddy): remove obsolete path-based Caddy template"
```

---

### Task 3: Update Role Defaults for Local Mode

**Files:**
- Modify: `ansible/roles/football_club_stack/defaults/main.yml`

- [ ] **Step 1: Replace `path` with `local` in derived variables**

Old content (`ansible/roles/football_club_stack/defaults/main.yml`):
```yaml
---
football_club_stack_dolibarr_url_root: >-
  {{ ('https://' ~ football_club_domain ~ '/club') if football_club_caddy_mode == 'path' else ('https://club.' ~ football_club_domain) }}

football_club_stack_invoiceninja_app_url: >-
  {{ ('https://' ~ football_club_domain ~ '/billing') if football_club_caddy_mode == 'path' else ('https://billing.' ~ football_club_domain) }}

football_club_stack_n8n_host: >-
  {{ (football_club_domain) if football_club_caddy_mode == 'path' else ('n8n.' ~ football_club_domain) }}

football_club_stack_n8n_webhook_url: >-
  {{ ('https://' ~ football_club_domain ~ '/n8n/') if football_club_caddy_mode == 'path' else ('https://n8n.' ~ football_club_domain ~ '/') }}
```

New content:
```yaml
---
football_club_stack_dolibarr_url_root: >-
  {{ 'https://club.lan' if football_club_caddy_mode == 'local' else 'https://club.' ~ football_club_domain }}

football_club_stack_invoiceninja_app_url: >-
  {{ 'https://billing.lan' if football_club_caddy_mode == 'local' else 'https://billing.' ~ football_club_domain }}

football_club_stack_n8n_host: >-
  {{ 'n8n.lan' if football_club_caddy_mode == 'local' else 'n8n.' ~ football_club_domain }}

football_club_stack_n8n_webhook_url: >-
  {{ 'https://n8n.lan/' if football_club_caddy_mode == 'local' else 'https://n8n.' ~ football_club_domain ~ '/' }}
```

**Verification:** `cat ansible/roles/football_club_stack/defaults/main.yml` shows new content.

- [ ] **Step 2: Commit**

```bash
git add ansible/roles/football_club_stack/defaults/main.yml
git commit -m "refactor(ansible): switch derived URLs from path to local mode"
```

---

### Task 4: Update Local VM Inventory

**Files:**
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`

- [ ] **Step 1: Change `football_club_caddy_mode` from `path` to `local`**

Old line (line 12):
```yaml
football_club_caddy_mode: "path"
```

New line:
```yaml
football_club_caddy_mode: "local"
```

**Verification:** `grep football_club_caddy_mode ansible/inventories/local_vm/group_vars/local_vm/vars.yml`

- [ ] **Step 2: Commit**

```bash
git add ansible/inventories/local_vm/group_vars/local_vm/vars.yml
git commit -m "fix(inventory): set local_vm caddy mode to local"
```

---

### Task 5: Update Validation Playbook

**Files:**
- Modify: `ansible/playbooks/validate.yml` (lines 32–49)

- [ ] **Step 1: Replace `path` with `local` in endpoint facts**

Old block:
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
```

New block:
```yaml
- name: Set service endpoint URLs
  ansible.builtin.set_fact:
    dolibarr_endpoint: >-
      {{ 'https://club.lan/' if football_club_caddy_mode == 'local'
         else 'https://club.' ~ football_club_domain ~ '/' }}
    billing_endpoint: >-
      {{ 'https://billing.lan/' if football_club_caddy_mode == 'local'
         else 'https://billing.' ~ football_club_domain ~ '/' }}
    n8n_endpoint: >-
      {{ 'https://n8n.lan/' if football_club_caddy_mode == 'local'
         else 'https://n8n.' ~ football_club_domain ~ '/' }}
    agreements_endpoint: >-
      {{ 'https://agreements.lan/' if football_club_caddy_mode == 'local'
         else 'https://agreements.' ~ football_club_domain ~ '/' }}
```

**Verification:** `grep -n "football_club_caddy_mode" ansible/playbooks/validate.yml`

- [ ] **Step 2: Commit**

```bash
git add ansible/playbooks/validate.yml
git commit -m "refactor(validate): update endpoint facts for local mode"
```

---

### Task 6: Update Implementation Plan Documentation

**Files:**
- Modify: `docs/implementation-plan.md` (Phase 1 Caddy configuration section, lines ~193–246)

- [ ] **Step 1: Replace path mode description with local mode**

Find the Caddy configuration subsection. It currently describes `subdomain` and `path` modes. Replace the path description with the new local mode.

Old content to replace (lines ~197–246 in current file):
```markdown
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

New content:
```markdown
Caddy routing mode is controlled by the `football_club_caddy_mode` inventory variable:

- `subdomain` — each service gets its own subdomain with ACME TLS (production default)
- `local` — `.lan` hostnames with Caddy internal TLS (local VM)

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

**Local mode Caddyfile:**

```
{
  http_port 80
  https_port 443
}

club.lan {
  tls internal
  reverse_proxy 127.0.0.1:8081
}

billing.lan {
  tls internal
  reverse_proxy 127.0.0.1:8082
}

n8n.lan {
  tls internal
  reverse_proxy 127.0.0.1:5678
}

agreements.lan {
  tls internal
  reverse_proxy 127.0.0.1:3000
}
```

Service containers receive correctly computed `*_URL` environment variables so self-referential links (emails, redirects, webhooks) match the external access pattern.

**Local client setup:**
After deploying the local VM, each Linux client needs the VM IP added to `/etc/hosts`:

```bash
sudo tee -a /etc/hosts <<EOF
192.168.x.x club.lan billing.lan n8n.lan agreements.lan
EOF
```

And Caddy's internal CA certificate imported:

```bash
scp user@vm:/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/caddy-local-ca.crt
sudo cp ~/caddy-local-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```
```

**Verification:** `grep -A 5 "Caddy routing mode" docs/implementation-plan.md` shows `local` instead of `path`.

- [ ] **Step 2: Commit**

```bash
git add docs/implementation-plan.md
git commit -m "docs: replace path mode with local .lan mode in Caddy docs"
```

---

### Task 7: Static Validation

**Verification:** Run Ansible lint and syntax checks.

- [ ] **Step 1: Run linting**

```bash
ansible-lint
yamllint .
ansible-playbook --syntax-check ansible/playbooks/site.yml
```

Expected: all pass with no errors.

- [ ] **Step 2: Commit (if any fixes needed)**

---

## Spec Coverage Check

| Spec Section | Implementing Task |
|---|---|
| Create `Caddyfile-local.j2` | Task 1 |
| Delete `Caddyfile-path.j2` | Task 2 |
| Update derived variables (`path` → `local`) | Task 3 |
| Update `local_vm` inventory | Task 4 |
| Update `validate.yml` | Task 5 |
| Update `docs/implementation-plan.md` | Task 6 |
| Static checks (lint, syntax-check) | Task 7 |

All spec requirements covered. No placeholders in plan.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-28-caddy-local-internal-tls.md`.

Choose approach:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans skill.
