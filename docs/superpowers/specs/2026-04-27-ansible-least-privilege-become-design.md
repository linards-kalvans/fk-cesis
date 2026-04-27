# Ansible Least-Privilege Become Design

## Context

The Ansible deployment foundation currently enables privilege escalation globally in `ansible/ansible.cfg` and at play level in both `site.yml` and `validate.yml`. This makes every task run with sudo even when the task only validates configuration, runs HTTP smoke checks, or interacts with Docker.

## Problem

Running all Ansible tasks as root increases blast radius and reduces auditability. The deployment still needs root for package installation, systemd service management, root-owned files under `/opt` and `/etc/caddy`, and root cron configuration. The deployment user is allowed to join the `docker` group so Docker and Compose actions can run without Ansible sudo.

## Goals

- Disable global Ansible privilege escalation.
- Remove play-level `become: true` from deployment and validation playbooks.
- Add task-level `become: true` only where root is required.
- Add the deployment user to the `docker` group.
- Run Docker Compose validation and lifecycle commands as the unprivileged deployment user.
- Run HTTP smoke checks without sudo.
- Preserve existing deployment architecture, service definitions, secrets model, and Caddy routes.

## Non-Goals

- Do not change Docker Compose service definitions except where required by privilege execution.
- Do not change Caddy routing or the Caddyfile template.
- Do not change Ansible Vault variable names or secret handling.
- Do not automate Stripe, imports, n8n workflows, OCR, WhatsApp, or Docuseal flows.
- Do not claim Docker group membership is a strong privilege boundary.

## Security Decision

Use least-privilege Ansible execution with Docker group access for the deployment user.

Why: task-level sudo makes privileged host mutations explicit and keeps harmless validations unprivileged. Docker group membership is accepted for this project because it enables deploy-user Compose operations without per-task sudo. The Docker group is root-equivalent, so this improves Ansible sudo minimization and auditability rather than creating a strict privilege boundary.

## Architecture

### Privilege Model

Ansible defaults to no privilege escalation. Playbooks also default to no escalation. Each root-required task declares `become: true` directly.

Root-required categories:

- apt package installation and cache updates;
- systemd service enable/start/reload;
- creation and modification of root-owned `/opt/*` paths;
- creation and modification of `/etc/caddy/*` paths;
- root cron jobs.

Unprivileged categories:

- Docker Compose config validation;
- Docker volume/container/Compose lifecycle commands after the deployment user has Docker group membership;
- HTTP smoke checks;
- readable Caddyfile validation where the file mode remains `0644`.

### Docker Access Model

The Docker role installs Docker with sudo, starts the service with sudo, adds `ansible_user` to the `docker` group with sudo, then resets the SSH connection so the new group membership is active for later unprivileged Docker commands.

### Validation Model

`validate.yml` runs unprivileged by default. Docker validation uses the deployment user's Docker group membership. HTTP checks use no sudo. Caddy validation uses no sudo while the Caddyfile is world-readable.

## Files Affected

- `ansible/ansible.cfg`: change privilege default to `become = False`.
- `ansible/playbooks/site.yml`: remove play-level `become: true`.
- `ansible/playbooks/validate.yml`: remove play-level `become: true`.
- `ansible/roles/common/tasks/main.yml`: add task-level sudo for package and directory tasks.
- `ansible/roles/docker/tasks/main.yml`: add task-level sudo, add deployment user to Docker group, reset SSH connection.
- `ansible/roles/football_club_stack/tasks/main.yml`: sudo only for root-owned rendered files; Docker commands unprivileged.
- `ansible/roles/caddy/tasks/main.yml`: sudo only for package, root file, backup, and service tasks; Caddy validation unprivileged.
- `ansible/roles/caddy/handlers/main.yml`: sudo for Caddy reload.
- `ansible/roles/backup/tasks/main.yml`: sudo for root-owned backup script and root cron.
- `tests/test_ansible_foundation.py`: add contract tests for the least-privilege model.
- `AGENTS.md`: document the workflow rule that Ansible uses task-level become only.

## Testing and Acceptance Criteria

- Contract tests fail before implementation and pass after implementation.
- `ansible.cfg` contains `become = False`.
- `site.yml` and `validate.yml` do not contain play-level `become: true`.
- Docker role appends `ansible_user` to the `docker` group.
- Docker role resets the SSH connection after group membership changes.
- Root-required tasks include task-level `become: true`.
- Docker and HTTP validation tasks do not use task-level or play-level sudo.
- `python3 -m unittest tests/test_ansible_foundation.py` passes.
- `ansible-lint` passes.
- `yamllint .` passes.
- `ansible-playbook ansible/playbooks/site.yml --syntax-check` passes.
- `ansible-playbook ansible/playbooks/validate.yml --syntax-check` passes.

## Approval State

The user approved this direction on 2026-04-27 with Docker group access allowed for the deployment user.
