# FK CĒSIS Environment Deployment Plan

## Context

This repository is the source of truth for repeatable deployment of the current FK CĒSIS operations environment.

Current active scope is limited to:

- InvoiceNinja for billing and payment operations
- Docuseal for document signing workflows
- Caddy for ingress and TLS termination
- backup automation for active service data

This repository does not currently own member management application development. The future in-house member management system will be built in a separate project and may be integrated into this deployment stack later through a separate approved spec and implementation plan.

## Architectural Principles

- Ansible is the source of truth for host configuration.
- Docker Compose remains the runtime orchestrator.
- Secrets are sourced from Ansible Vault only and rendered onto the target host.
- Caddy owns inbound routing and TLS termination for the active services.
- Backups cover active persistent data only.
- Do not plan around Dolibarr, n8n, or DocTR in this repository's current scope.

## Managed Runtime

| Service | Role | Image |
|---|---|---|
| **InvoiceNinja** | Billing, invoices, payment tracking | `invoiceninja/invoiceninja-octane:latest` |
| **Docuseal** | Agreement/document signing | `docuseal/docuseal:latest` |
| **Caddy** | Reverse proxy and TLS termination | Host package / managed config |

InvoiceNinja requires MariaDB and Redis as supporting runtime services inside the Compose project.

## Current Milestones

### Milestone 1 — Scope Alignment

- Remove old platform assumptions from source-of-truth docs.
- Keep `AGENTS.md`, Ansible docs, and active specs aligned to the reduced service set.
- Preserve a clear extension point for the future in-house member management service.

### Milestone 2 — Repeatable Deployment Foundation

- Provision an Ubuntu LTS host over SSH with Ansible.
- Install Docker Engine and Docker Compose plugin.
- Render `/opt/football-club/docker-compose.yml` and `/opt/football-club/.env` from repository templates.
- Install Caddy, manage a dedicated FK CĒSIS route snippet, and ensure the host-owned `/etc/caddy/Caddyfile` imports it.
- Start the active stack.

### Milestone 3 — Validation and Recovery

- Run mandatory Ansible lint and syntax checks.
- Validate the deployed active endpoints.
- Verify backup generation for active service data.
- Document operator recovery steps until executable restore tests exist.

### Milestone 4 — Future Member System Integration Readiness

- Keep repo structure ready for an additional service behind Caddy.
- Require a new approved spec and plan before adding the in-house member management system to the playbook.

## Ansible Deployment Foundation

The deployment foundation targets a local Ubuntu LTS VM first and a production-style Ubuntu LTS host later. Ansible owns these host artifacts:

- `/opt/football-club/docker-compose.yml`
- `/opt/football-club/.env`
- `/etc/caddy/football-club-routes.caddy`
- `/opt/football-club/backup.sh`
- backup cron schedule

The main `/etc/caddy/Caddyfile` remains the host-owned entrypoint. The playbook preserves that file and ensures it imports the FK CĒSIS-managed snippet.

Secrets must come from Ansible Vault. Never commit generated `.env` files, vault passwords, API tokens, Stripe secrets, database passwords, or other plaintext credentials.

Mandatory checks for Ansible changes:

```bash
ansible-lint
yamllint .
ansible-playbook --syntax-check ansible/playbooks/site.yml
ansible-playbook --check --diff ansible/playbooks/site.yml
```

After dry-run, apply the playbook to the Ubuntu LTS VM and run HTTP smoke checks against the active service endpoints.

## Target Routing Model

Caddy routing mode is controlled by the `football_club_caddy_mode` inventory variable:

- `subdomain` — production-style routing with ACME TLS
- `local` — `.lan` hostnames with Caddy internal TLS

### Production-style hostnames

- `billing.<domain>` → InvoiceNinja
- `agreements.<domain>` → Docuseal

### Local hostnames

- `billing.lan` → InvoiceNinja
- `agreements.lan` → Docuseal

The future in-house member management system does not have an assigned hostname in this repo yet.

## Backup Scope

Backup automation should cover only active persistent data:

- InvoiceNinja database dump
- InvoiceNinja persistent storage volume(s)
- Docuseal persistent data volume

If Caddy-managed certificates or supporting runtime state require explicit backup in a future iteration, add that through a separate approved change.

## Validation Checklist

Current-scope validation should confirm only active services.

### Static checks

- `ansible-lint`
- `yamllint .`
- `ansible-playbook --syntax-check ansible/playbooks/site.yml`
- `ansible-playbook --syntax-check ansible/playbooks/validate.yml`

### Dry run

- `ansible-playbook --check --diff ansible/playbooks/site.yml`

### Host/runtime checks

- `docker compose -f /opt/football-club/docker-compose.yml config` succeeds
- expected active containers are running
- Caddy validates and reloads successfully
- HTTP smoke checks pass for `billing` and `agreements` endpoints in the selected routing mode

### Manual recovery expectation

Until restore automation exists, the operator should be able to:

- locate the latest backup artifacts
- restore InvoiceNinja database data into a temporary test environment or documented restore path
- restore InvoiceNinja persistent storage
- restore Docuseal persistent data

## Out of Scope

The following are explicitly out of scope for this repository's current plan:

- Dolibarr deployment or configuration
- n8n deployment or workflow automation
- DocTR OCR service deployment
- member import automation
- attendance workflows
- WhatsApp automation
- OCR-based registration
- implementation details for the future in-house member management system
- regenerating `docs/html/implementation-plan.html`

## Risks and Constraints

| Risk | Impact | Mitigation |
|---|---|---|
| Docs drift from active playbook scope | Operators deploy the wrong service set | Keep `AGENTS.md`, specs, and this plan aligned in the same change |
| Backups are present but untested | Recovery confidence is low | Keep manual restore steps documented and validate them before claiming production readiness |
| Future member-system work leaks into this repo too early | Scope ambiguity and rework | Require a dedicated approved spec and plan before adding it here |
| Secret handling mistakes | Credential exposure | Use Ansible Vault only; never commit plaintext runtime secrets |

## Environment Variables and Secrets

Document only active-service secrets in this repository's current source-of-truth docs.

Example categories:

- InvoiceNinja application key and admin credentials
- InvoiceNinja database credentials
- Docuseal secret key
- domain/admin email values needed for Caddy and service URLs
- backup destination or retention settings if the playbook introduces them

Do not add placeholders here for removed services.

## Future Integration Note

The future in-house member management system may later be added to this deployment repository. When that happens, add a dedicated design spec and implementation plan first, then extend:

- Compose templates
- Caddy routing
- Vault/example secrets
- validation checks
- backup scope

Do not assume its runtime, database, or hostname before that design work exists.
