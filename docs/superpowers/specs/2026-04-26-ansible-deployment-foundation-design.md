# Ansible Deployment Foundation Design

## Context

FK CĒSIS needs a repeatable deployment foundation for the active operations environment described in `docs/implementation-plan.md`. The repository scope was narrowed on 2026-05-04 to infrastructure automation and operator documentation for InvoiceNinja, Docuseal, Caddy, and backups only.

The first implementation step remains replacing manual host changes with Ansible-managed infrastructure as code while keeping Docker Compose as the runtime orchestrator.

## Problem

The environment must be deployable from source-controlled automation before later integrations are considered. The deployment must work first against a local Ubuntu LTS VM over SSH, then later against a production-style Ubuntu LTS host. The production host may already have Caddy running; Ansible will take ownership of the Caddy configuration after backing up the existing file.

## Goals

- Provision an Ubuntu LTS VM over SSH.
- Install and configure Docker Engine and the Docker Compose plugin.
- Create `/opt/football-club` and render the active Compose project there.
- Render `/opt/football-club/.env` from encrypted Ansible Vault variables only.
- Install and configure Caddy, with Ansible owning the full Caddyfile.
- Install the backup script and schedule.
- Start the active stack.
- Verify the stack through mandatory linting, syntax checks, dry run, runtime checks, and HTTP smoke checks.
- Preserve a clean extension point for a future in-house member management service.

## Non-Goals

- Do not automate member import.
- Do not automate Stripe verification or payment acceptance testing.
- Do not deploy Dolibarr, n8n, or DocTR in the current-scope design.
- Do not bootstrap future member-system application settings.
- Do not update `docs/html/implementation-plan.html`; it may remain stale.

## Recommended Approach

Use Ansible to provision hosts and render Docker Compose runtime configuration. Docker Compose remains the local service orchestrator. This is the best fit because it is repeatable, understandable, works well with one or a few hosts, and remains easy to hand over compared with heavier alternatives.

Alternatives considered:

1. Terraform/OpenTofu plus Ansible. Useful later for DNS, firewalling, or external infrastructure, but unnecessary for the current host-focused goal.
2. NixOS or Colmena. Stronger reproducibility, but added operational complexity is a poor fit for club handover.

## Architecture

### Deployment Model

The repository is the source of truth for deployment automation. Ansible targets environment-specific inventories:

- `local_vm` for the first Ubuntu LTS VM validation target
- `production` for the later production-style host

Both environments use the same roles and templates. Inventory variables define domains, email addresses, paths, and environment-specific behavior.

### Runtime Model

Docker Compose runs the application stack. Ansible renders and manages these host files:

- `/opt/football-club/docker-compose.yml`
- `/opt/football-club/.env`
- `/etc/caddy/Caddyfile`
- `/opt/football-club/backup.sh`
- backup cron entry

Ansible starts and restarts the stack through Docker Compose.

### Active Service Set

The active runtime described by this design consists of:

- InvoiceNinja
- supporting InvoiceNinja runtime services such as MariaDB and Redis
- Docuseal
- Caddy
- backup automation

This design no longer treats Dolibarr, n8n, or DocTR as active-scope services.

### Secrets Model

Secrets are stored in encrypted Ansible Vault files:

- `ansible/inventories/local_vm/group_vars/local_vm/vault.yml`
- `ansible/inventories/production/group_vars/production/vault.yml`

Only encrypted vault files may contain real secrets. Safe examples are committed for operators:

- `vault.example.yml`
- `.env.example` when needed

Vault password files, generated `.env` files, API keys, database passwords, Stripe secrets, and other plaintext secrets must never be committed.

### Caddy Model

Ansible installs and manages Caddy. On a host where Caddy already exists, the existing main Caddyfile is backed up before Ansible replaces it. The project Caddyfile contains routes for:

- `billing.<domain>` to InvoiceNinja
- `agreements.<domain>` to Docuseal

The local VM mode uses only:

- `billing.lan`
- `agreements.lan`

A future member service can be added later through a separate approved change.

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
    validate.yml
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

All of these checks are mandatory for Ansible changes:

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
   - expected active containers are running or healthy where health checks exist.
   - Caddy validates and reloads successfully.
   - HTTP smoke checks pass for `billing` and `agreements` endpoints in the selected routing mode.

Out of scope for this test cycle:

- real payment-gateway acceptance verification;
- future member-system integration;
- any Dolibarr, n8n, or DocTR behavior.

## Documentation Updates Required

- Keep `docs/implementation-plan.md` aligned with the narrowed service set.
- Keep `AGENTS.md` aligned with active repo ownership and workflow rules.
- Keep `ansible/README.md` aligned with the active endpoints, vault workflow, and validation commands.
- Leave `docs/html/implementation-plan.html` stale unless a separate documentation-rendering task is approved.

## Approval State

Originally approved on 2026-04-26 for the Ansible-first provisioning approach.

Reinterpreted on 2026-05-04 under the approved scope reduction so it applies only to the active service set in this repository.
