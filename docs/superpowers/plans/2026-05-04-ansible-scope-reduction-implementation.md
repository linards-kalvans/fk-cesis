# Ansible Scope Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the active Ansible implementation and nearby planning artifacts with the approved reduced repo scope: InvoiceNinja, Docuseal, Caddy, and backups only.

**Architecture:** Remove Dolibarr, n8n, and DocTR from the live Ansible stack, validation, Caddy routing, backup script, and vault examples. Keep the repo's current runtime centered on InvoiceNinja and Docuseal, while trimming legacy source-of-truth references so current guidance matches the implementation.

**Tech Stack:** Ansible, Docker Compose, Caddy, Jinja templates, Bash, Markdown.

---

## Source Documents

- Scope spec: `docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md`
- Deployment foundation spec: `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`
- Active plan: `docs/implementation-plan.md`
- Project instructions: `AGENTS.md`

## File Structure

Modify these live implementation files:

- `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`: active service/runtime definition
- `ansible/roles/football_club_stack/templates/env.j2`: active runtime secret/env rendering
- `ansible/roles/football_club_stack/defaults/main.yml`: active public URL defaults
- `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`: production-style routes
- `ansible/roles/caddy/templates/Caddyfile-local.j2`: local `.lan` routes
- `ansible/roles/backup/templates/backup.sh.j2`: active backup coverage
- `ansible/playbooks/validate.yml`: smoke-test URLs and checks
- `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`: local example secrets
- `ansible/inventories/production/group_vars/production/vault.example.yml`: production example secrets
- `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`: remove dead flags if present
- `ansible/inventories/production/group_vars/production/vars.yml`: remove dead flags if present

Modify these planning/history files to reduce misleading current-scope references:

- `docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md`
- `docs/superpowers/plans/2026-04-27-caddy-routing-modes.md`
- `docs/superpowers/plans/2026-04-28-caddy-local-internal-tls.md`
- `docs/superpowers/specs/2026-04-27-caddy-routing-modes-design.md`
- `docs/superpowers/specs/2026-04-28-caddy-local-internal-tls-design.md`

## Test Strategy

Primary verification is Ansible-oriented because these changes are templates, inventory examples, shell snippets, and docs.

Use this sequence:

1. Red check: confirm legacy services are still present before editing.
2. Change implementation files.
3. Run mandatory checks:
   - `ANSIBLE_CONFIG=ansible/ansible.cfg ansible-lint ansible/playbooks/site.yml ansible/playbooks/validate.yml`
   - `yamllint .`
   - `ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml`
   - `ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml`
4. Green check: confirm live implementation files no longer contain Dolibarr, `n8n`, or DocTR references.
5. Green check: confirm trimmed plan/spec files are explicitly historical or aligned to the reduced scope.

## Task 1: Remove legacy services from the live Ansible stack

**Files:**
- Modify: `ansible/roles/football_club_stack/templates/docker-compose.yml.j2`
- Modify: `ansible/roles/football_club_stack/templates/env.j2`
- Modify: `ansible/roles/football_club_stack/defaults/main.yml`
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml`
- Modify: `ansible/inventories/production/group_vars/production/vault.example.yml`
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`
- Modify: `ansible/inventories/production/group_vars/production/vars.yml`

- [ ] **Step 1: Write the failing red check**

```bash
rg -n "dolibarr|DOLI_|n8n|N8N_|doctr|DocTR" \
  ansible/roles/football_club_stack/templates/docker-compose.yml.j2 \
  ansible/roles/football_club_stack/templates/env.j2 \
  ansible/roles/football_club_stack/defaults/main.yml \
  ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml \
  ansible/inventories/production/group_vars/production/vault.example.yml \
  ansible/inventories/local_vm/group_vars/local_vm/vars.yml \
  ansible/inventories/production/group_vars/production/vars.yml
```

Expected: matches for removed-service runtime, secret, and dead inventory entries.

- [ ] **Step 2: Remove the legacy runtime/env/defaults entries**

Implementation requirements:

```text
- Delete Dolibarr services, DB, env vars, and volumes from docker-compose template.
- Delete n8n services, DB, env vars, and volumes from docker-compose template.
- Delete DocTR service from docker-compose template.
- Keep InvoiceNinja + MariaDB + Redis + nginx + Docuseal only.
- Remove DOLI_* and N8N_* entries from env.j2.
- Reduce defaults/main.yml to the active public URLs only.
- Remove `football_club_doctr_enabled` and n8n-related example secrets from inventory examples.
```

- [ ] **Step 3: Run the red check again and verify it now fails cleanly**

Run the same `rg` command from Step 1.
Expected: no matches.

## Task 2: Remove legacy routes and smoke checks from Caddy/validation/backup

**Files:**
- Modify: `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
- Modify: `ansible/roles/caddy/templates/Caddyfile-local.j2`
- Modify: `ansible/playbooks/validate.yml`
- Modify: `ansible/roles/backup/templates/backup.sh.j2`

- [ ] **Step 1: Write the failing red check**

```bash
rg -n "club\\.|club\\.lan|n8n\\.|n8n\\.lan|dolibarr|n8n|doctr" \
  ansible/roles/caddy/templates/Caddyfile-subdomain.j2 \
  ansible/roles/caddy/templates/Caddyfile-local.j2 \
  ansible/playbooks/validate.yml \
  ansible/roles/backup/templates/backup.sh.j2
```

Expected: routes, endpoints, and backup commands for removed services are present.

- [ ] **Step 2: Remove the legacy routes, checks, and backup coverage**

Implementation requirements:

```text
- Keep only `billing` and `agreements` routes in both Caddy templates.
- Keep only `billing_endpoint` and `agreements_endpoint` in validate.yml.
- Keep only HTTP checks for InvoiceNinja and Docuseal.
- Keep only backup commands for InvoiceNinja DB/storage and Docuseal data.
- Remove Dolibarr and n8n dump/archive commands entirely.
```

- [ ] **Step 3: Run the red check again and verify it now fails cleanly**

Run the same `rg` command from Step 1.
Expected: no matches.

## Task 3: Trim misleading current-scope plan/spec artifacts

**Files:**
- Modify: `docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md`
- Modify: `docs/superpowers/plans/2026-04-27-caddy-routing-modes.md`
- Modify: `docs/superpowers/plans/2026-04-28-caddy-local-internal-tls.md`
- Modify: `docs/superpowers/specs/2026-04-27-caddy-routing-modes-design.md`
- Modify: `docs/superpowers/specs/2026-04-28-caddy-local-internal-tls-design.md`

- [ ] **Step 1: Write the failing red check**

```bash
rg -n "club\\.<domain>|club\\.lan|n8n\\.<domain>|n8n\\.lan|Dolibarr|n8n|DocTR|doctr" \
  docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md \
  docs/superpowers/plans/2026-04-27-caddy-routing-modes.md \
  docs/superpowers/plans/2026-04-28-caddy-local-internal-tls.md \
  docs/superpowers/specs/2026-04-27-caddy-routing-modes-design.md \
  docs/superpowers/specs/2026-04-28-caddy-local-internal-tls-design.md
```

Expected: these historical docs still read like active source-of-truth for removed services.

- [ ] **Step 2: Add explicit historical/superseded framing and trim the most misleading current-scope claims**

Implementation requirements:

```text
- Add a short top-note to each file stating it is historical/superseded by the 2026-05-04 scope-reduction spec for current repo scope.
- Do not fully rewrite these files; keep history intact.
- Where easy and low-risk, adjust the most misleading “current active” language near the top of the file.
```

- [ ] **Step 3: Run the red check again and verify the files now clearly declare themselves historical**

```bash
rg -n "historical|superseded|2026-05-04-ansible-scope-reduction-design.md" \
  docs/superpowers/plans/2026-04-26-ansible-deployment-foundation.md \
  docs/superpowers/plans/2026-04-27-caddy-routing-modes.md \
  docs/superpowers/plans/2026-04-28-caddy-local-internal-tls.md \
  docs/superpowers/specs/2026-04-27-caddy-routing-modes-design.md \
  docs/superpowers/specs/2026-04-28-caddy-local-internal-tls-design.md
```

Expected: every file contains an explicit historical/superseded note.

## Task 4: Verify the narrowed implementation end to end

**Files:**
- No new files

- [ ] **Step 1: Run mandatory static verification**

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-lint ansible/playbooks/site.yml ansible/playbooks/validate.yml
yamllint .
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
```

Expected: all commands exit 0.

- [ ] **Step 2: Run final green checks for live implementation scope**

```bash
rg -n "dolibarr|DOLI_|n8n|N8N_|doctr|DocTR|club\\.lan|club\\.\\{|n8n\\.lan|n8n\\.\\{" \
  ansible/ AGENTS.md docs/implementation-plan.md ansible/README.md \
  -g '!docs/html/**'
```

Expected: no matches in live Ansible implementation files; any remaining matches should be confined to historical docs or explicit out-of-scope notes.

- [ ] **Step 3: Review the diff before completion**

```bash
git diff -- AGENTS.md ansible/README.md docs/implementation-plan.md \
  docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md \
  docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md \
  ansible/roles/football_club_stack/templates/docker-compose.yml.j2 \
  ansible/roles/football_club_stack/templates/env.j2 \
  ansible/roles/football_club_stack/defaults/main.yml \
  ansible/roles/caddy/templates/Caddyfile-subdomain.j2 \
  ansible/roles/caddy/templates/Caddyfile-local.j2 \
  ansible/playbooks/validate.yml \
  ansible/roles/backup/templates/backup.sh.j2
```

Expected: diff shows only the intended scope reduction and historical-note changes.
