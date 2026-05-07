# Caddy Imported Snippet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the Caddy role so Ansible preserves the host-owned main Caddyfile, manages FK CĒSIS routes in a separate snippet, and ensures the main file imports that snippet.

**Architecture:** Add a narrow regression test playbook that exercises the caddy role against temporary files on localhost. Then change the role to render a dedicated snippet, ensure a single `import` line in the main Caddyfile, and keep validation pointed at the main config entrypoint. Update active docs so they no longer say Ansible replaces the whole main Caddyfile.

**Tech Stack:** Ansible, Jinja2, Caddy

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `ansible/tests/caddy_import_snippet.yml` | Create | Local regression test for preserve-and-import behavior |
| `ansible/roles/caddy/tasks/main.yml` | Modify | Stop overwriting the main file; manage snippet + ensured import |
| `ansible/roles/caddy/templates/Caddyfile-subdomain.j2` | Modify | Render only FK CĒSIS route blocks, no global options |
| `ansible/roles/caddy/templates/Caddyfile-local.j2` | Modify | Render only FK CĒSIS route blocks, no global options |
| `ansible/inventories/local_vm/group_vars/local_vm/vars.yml` | Modify | Add snippet path variable |
| `ansible/inventories/production/group_vars/production/vars.yml` | Modify | Add snippet path variable |
| `docs/implementation-plan.md` | Modify | Update current source-of-truth wording about Caddy ownership |
| `ansible/README.md` | Modify | Update operator docs for snippet/import ownership model |

### Task 1: Add the Failing Regression Test

**Files:**
- Create: `ansible/tests/caddy_import_snippet.yml`

- [ ] **Step 1: Write the failing test**

Create `ansible/tests/caddy_import_snippet.yml`:

```yaml
---
- name: Regression test for imported Caddy snippet
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    test_root: "/tmp/fk-cesis-caddy-test"
    football_club_domain: "example.lv"
    football_club_admin_email: "admin@example.lv"
    football_club_caddy_mode: "subdomain"
    football_club_caddyfile_path: "{{ test_root }}/Caddyfile"
    football_club_caddy_backup_dir: "{{ test_root }}/backups"
    football_club_caddy_snippet_path: "{{ test_root }}/football-club-routes.caddy"

  tasks:
    - name: Reset test directory
      ansible.builtin.file:
        path: "{{ test_root }}"
        state: absent

    - name: Recreate test directory
      ansible.builtin.file:
        path: "{{ test_root }}"
        state: directory
        mode: "0755"

    - name: Seed host-owned main Caddyfile
      ansible.builtin.copy:
        dest: "{{ football_club_caddyfile_path }}"
        mode: "0644"
        content: |
          {
            email ops@example.lv
          }

          existing.example.lv {
            respond "host-owned"
          }

    - name: Include caddy role
      ansible.builtin.include_role:
        name: caddy

    - name: Read main Caddyfile after role
      ansible.builtin.slurp:
        src: "{{ football_club_caddyfile_path }}"
      register: caddy_main_file

    - name: Read snippet after role
      ansible.builtin.slurp:
        src: "{{ football_club_caddy_snippet_path }}"
      register: caddy_snippet_file

    - name: Assert main file is preserved and imports snippet once
      ansible.builtin.assert:
        that:
          - "'existing.example.lv' in (caddy_main_file.content | b64decode)"
          - "((caddy_main_file.content | b64decode) | regex_findall('(?m)^import {{ football_club_caddy_snippet_path | regex_escape }}$') | length) == 1"
          - "'billing.example.lv' in (caddy_snippet_file.content | b64decode)"
          - "'agreements.example.lv' in (caddy_snippet_file.content | b64decode)"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/caddy_import_snippet.yml
```

Expected: FAIL because the current role writes the rendered template directly to `football_club_caddyfile_path` and never creates `football_club_caddy_snippet_path`.

- [ ] **Step 3: Commit**

```bash
git add ansible/tests/caddy_import_snippet.yml
git commit -m "test(caddy): add imported snippet regression test"
```

### Task 2: Make the Role Pass the Regression Test

**Files:**
- Modify: `ansible/roles/caddy/tasks/main.yml`
- Modify: `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
- Modify: `ansible/roles/caddy/templates/Caddyfile-local.j2`
- Modify: `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`
- Modify: `ansible/inventories/production/group_vars/production/vars.yml`

- [ ] **Step 1: Write the minimal role change**

Update the inventory vars files to define:

```yaml
football_club_caddy_snippet_path: "/etc/caddy/football-club-routes.caddy"
```

Update `ansible/roles/caddy/tasks/main.yml` so it:

1. keeps the existing install and backup-directory tasks;
2. stats the main Caddyfile;
3. backs up the main Caddyfile before first takeover as it does now;
4. creates a minimal main Caddyfile with only the import line if the file does not exist;
5. renders `Caddyfile-{{ football_club_caddy_mode }}.j2` to `{{ football_club_caddy_snippet_path }}`;
6. ensures exactly one line `import {{ football_club_caddy_snippet_path }}` exists in `{{ football_club_caddyfile_path }}`;
7. validates the main file with `caddy validate --config {{ football_club_caddyfile_path }} --adapter caddyfile`.

Update both route templates so they contain only the site blocks. Remove global option blocks such as:

```jinja2
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
}
```

and, in production, remove the global `email` stanza from the snippet as well.

- [ ] **Step 2: Run the regression test to verify it passes**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/caddy_import_snippet.yml
```

Expected: PASS, with the seeded host-owned site still present in the main file and the FK CĒSIS routes rendered into the separate snippet.

- [ ] **Step 3: Re-run the regression test to verify idempotent behavior**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/tests/caddy_import_snippet.yml
```

Expected: PASS again with the same assertions and no duplicate import line.

- [ ] **Step 4: Commit**

```bash
git add ansible/roles/caddy/tasks/main.yml \
  ansible/roles/caddy/templates/Caddyfile-subdomain.j2 \
  ansible/roles/caddy/templates/Caddyfile-local.j2 \
  ansible/inventories/local_vm/group_vars/local_vm/vars.yml \
  ansible/inventories/production/group_vars/production/vars.yml
git commit -m "feat(caddy): manage imported route snippet"
```

### Task 3: Align Active Documentation

**Files:**
- Modify: `docs/implementation-plan.md`
- Modify: `ansible/README.md`

- [ ] **Step 1: Update the docs**

In both files, replace wording that says Ansible manages or replaces `/etc/caddy/Caddyfile` with wording that says:

- the host-owned main file remains the entrypoint;
- FK CĒSIS routes are rendered to a dedicated snippet;
- the role ensures an `import` line for that snippet.

- [ ] **Step 2: Verify the docs point to the new ownership model**

Run:
```bash
rg -n "manage /etc/caddy/Caddyfile|Ansible owns the full Caddyfile|Render managed Caddyfile" docs/implementation-plan.md ansible/README.md
```

Expected: no active-source-of-truth wording that claims the full main Caddyfile is replaced by Ansible.

- [ ] **Step 3: Commit**

```bash
git add docs/implementation-plan.md ansible/README.md
git commit -m "docs(caddy): describe imported snippet ownership"
```

### Task 4: Run Required Project Verification

**Files:**
- Test: `ansible/tests/caddy_import_snippet.yml`
- Test: `ansible/playbooks/site.yml`
- Test: `ansible/playbooks/validate.yml`

- [ ] **Step 1: Run Ansible lint**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-lint ansible/playbooks/site.yml ansible/playbooks/validate.yml ansible/tests/caddy_import_snippet.yml
```

Expected: PASS

- [ ] **Step 2: Run YAML lint**

Run:
```bash
yamllint .
```

Expected: PASS

- [ ] **Step 3: Run syntax checks**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/tests/caddy_import_snippet.yml
```

Expected: PASS

- [ ] **Step 4: Run dry run**

Run:
```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff ansible/playbooks/site.yml --ask-vault-pass
```

Expected: PASS if vault access and inventory connectivity are available. If not available in the current environment, record the exact blocker.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(ansible): verify imported caddy snippet change"
```
