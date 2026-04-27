# Ansible Deployment Foundation Design

## Context

FK CĒSIS needs a repeatable deployment foundation for the hybrid club management platform described in `docs/implementation-plan.md`. The current plan describes manual Docker Compose, Caddy, secrets, and backup steps. The first implementation step will replace those manual host changes with Ansible-managed infrastructure as code while preserving the existing service architecture and phase gates.

## Problem

The platform must be deployable from source-controlled automation before application-specific configuration and workflow automation are added. The deployment must work first against a local Ubuntu LTS VM over SSH, then later against a production Ubuntu LTS host. The production host may already have Caddy running; Ansible will take ownership of the Caddy configuration after backing up the existing file.

## Goals

- Provision an Ubuntu LTS VM over SSH.
- Install and configure Docker Engine and the Docker Compose plugin.
- Create `/opt/football-club` and render the platform Compose project there.
- Render `/opt/football-club/.env` from encrypted Ansible Vault variables only.
- Install and configure Caddy, with Ansible owning the full Caddyfile.
- Install the backup script and schedule.
- Start the stack with Docker Compose.
- Verify the stack through mandatory linting, syntax checks, dry run, runtime checks, and HTTP smoke checks.
- Keep the existing Dolibarr, InvoiceNinja, n8n, Docuseal, DocTR, Stripe, and Caddy architecture intact.

## Non-Goals

- Do not automate member import in this first iteration.
- Do not automate Stripe verification; it remains a manual Phase 1 gate with a real Latvian bank account.
- Do not create n8n workflows yet.
- Do not bootstrap application settings through APIs yet.
- Do not automate WhatsApp, OCR registration, or agreement flows yet.
- Do not update `docs/html/implementation-plan.html`; it may remain stale.

## Recommended Approach

Use Ansible to provision hosts and render Docker Compose runtime configuration. Docker Compose remains the local service orchestrator. This is the best fit because it is repeatable, understandable, works well with one or a few hosts, and remains easy to hand over compared with heavier alternatives.

Alternatives considered:

1. Terraform/OpenTofu plus Ansible. This is useful later for cloud infrastructure, DNS, and firewall automation, but it is unnecessary for the current local-VM-first goal.
2. NixOS or Colmena. This provides stronger reproducibility but adds operational complexity and is a poor fit for club handover.

## Architecture

### Deployment Model

The repository becomes the source of truth for deployment automation. Ansible targets environment-specific inventories:

- `local_vm` for the first Ubuntu LTS VM validation target.
- `production` for the later production host.

Both environments use the same roles and templates. Inventory variables define hostnames, domains, email addresses, paths, and environment-specific behavior.

### Runtime Model

Docker Compose runs the application stack. Ansible renders and manages these host files:

- `/opt/football-club/docker-compose.yml`
- `/opt/football-club/.env`
- `/etc/caddy/Caddyfile`
- `/opt/football-club/backup.sh`
- backup cron entry

Ansible starts and restarts the stack through Docker Compose.

### Secrets Model

Secrets are stored in encrypted Ansible Vault files:

- `ansible/inventories/local_vm/group_vars/local_vm/vault.yml`
- `ansible/inventories/production/group_vars/production/vault.yml`

Only encrypted vault files may contain real secrets. Safe examples are committed for operators:

- `vault.example.yml`
- `.env.example`

Vault password files, generated `.env` files, API keys, database passwords, Stripe secrets, WhatsApp tokens, and real ID document photos must never be committed.

### Caddy Model

Ansible installs and manages Caddy. On a host where Caddy already exists, the existing main Caddyfile is backed up before Ansible replaces it. The project Caddyfile contains routes for:

- `club.<domain>` to Dolibarr
- `billing.<domain>` to InvoiceNinja
- `n8n.<domain>` to n8n
- `agreements.<domain>` to Docuseal

The local VM smoke test uses real subdomains pointed to the VM.

## Proposed Repository Structure

```text
ansible/
  ansible.cfg
  requirements.yml
  inventories/
    local_vm/hosts.yml
    production/hosts.yml
  group_vars/
    local_vm/
      vars.yml
      vault.example.yml
      vault.yml
    production/
      vars.yml
      vault.example.yml
      vault.yml
  playbooks/
    site.yml
  roles/
    common/
    docker/
    football_club_stack/
    caddy/
    backup/
  templates/
    docker-compose.yml.j2
    env.j2
    Caddyfile.j2
    backup.sh.j2
```

Role responsibilities:

- `common`: baseline packages, users, directories, and minimal safe host defaults.
- `docker`: Docker Engine and Compose plugin installation.
- `football_club_stack`: application directory, Compose file, environment file, and stack lifecycle.
- `caddy`: Caddy installation, existing config backup, managed Caddyfile, validation, and reload.
- `backup`: backup script and cron schedule.

## Testing and Acceptance Criteria

All of these checks are mandatory for the first Ansible change:

1. Static checks:
   - `ansible-lint`
   - `yamllint`
   - `ansible-playbook --syntax-check`
2. Dry run:
   - `ansible-playbook --check --diff`
3. Apply to Ubuntu LTS VM:
   - full playbook run succeeds.
4. Runtime checks on the VM:
   - `docker compose -f /opt/football-club/docker-compose.yml config` succeeds.
   - expected containers are running or healthy where health checks exist.
   - Caddy validates and reloads successfully.
   - HTTP smoke checks pass for `club.<domain>`, `billing.<domain>`, `n8n.<domain>`, and `agreements.<domain>`.

Out of scope for this first test cycle:

- real Stripe payment verification;
- member import correctness;
- n8n workflows;
- DocTR OCR;
- WhatsApp messaging.

The existing Phase 1 gate remains unchanged: do not proceed to Phase 2 until Stripe Latvia SEPA and card payments are confirmed with a real bank account.

## Documentation Updates Required

- Update `docs/implementation-plan.md` so Phase 1 describes Ansible-managed deployment instead of manual host edits.
- Update `AGENTS.md` so project workflow names Ansible, Ansible Vault, mandatory `ansible-lint`, mandatory `yamllint`, and the stale rendered HTML decision.
- Leave `docs/html/implementation-plan.html` stale unless a separate documentation-rendering task is approved.

## Approval State

The design was approved by the user on 2026-04-26 with Option A: Ansible-first provisioning and Docker Compose runtime.
