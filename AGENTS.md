# Project Overview

Ansible deployment and operations documentation repo for FK CĒSIS. The repo is used to keep the club environment repeatable across local VM and future production-style hosts. Application/product development for the future in-house member management system will happen in a separate project until an approved integration scope is added here.

## Scope

- Maintain repeatable Ansible deployment for InvoiceNinja, Docuseal, Caddy, and backup automation.
- Keep deployment docs, operator workflows, and secret-handling guidance aligned with the active stack.
- Preserve room to add the future in-house member management system later, but do not define or implement it in this repo yet.
- Do not treat Dolibarr, n8n, or DocTR as current-scope services in this repository.

## Milestones

- Milestone 1: narrow source-of-truth docs to the active deployment scope.
- Milestone 2: keep local VM and production-style deployment repeatable for InvoiceNinja, Docuseal, Caddy, and backups.
- Milestone 3: document validated operator workflows for secrets, deploy, smoke checks, and recovery.
- Milestone 4: add the future in-house member management system only after a separate approved spec and plan exist.

## Specs

- Approved design specs live under `docs/superpowers/specs/`.
- Current scope-change spec: `docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md`.
- Current Caddy ownership spec: `docs/superpowers/specs/2026-05-07-caddy-imported-snippet-design.md`.
- Deployment foundation spec remains relevant where it does not conflict with the scope-change spec: `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`.
- `docs/html/implementation-plan.html` is a rendered historical companion and may be stale; update Markdown first if content changes, and only regenerate HTML when explicitly in scope.

## Plans

- Current active planning/documentation source of truth: `docs/implementation-plan.md`, narrowed by `docs/superpowers/specs/2026-05-04-ansible-scope-reduction-design.md`.
- For Caddy ownership, the active intent is to preserve the host-owned main Caddyfile and let Ansible manage only a dedicated imported snippet plus the required `import` line.
- If older plans or specs mention Dolibarr, n8n, or DocTR as active scope, the newer scope-reduction spec overrides them.
- Do not add implementation details for the future in-house member management system unless a new approved spec and plan are added in the same change.

## Tech Stack

- Ansible is the deployment automation tool.
- Docker Compose remains the runtime orchestrator.
- InvoiceNinja: `invoiceninja/invoiceninja-octane:latest` with MariaDB.
- Docuseal: `docuseal/docuseal:latest` with SQLite volume.
- Caddy provides reverse proxy and TLS termination.
- Ansible-managed club routes should live in a dedicated Caddy snippet imported from the host's main Caddyfile, not by replacing the whole main file.
- Ansible Vault is required for committed encrypted secrets.
- Backup automation covers active service data and databases only.

## Workflow Rules

- This repo was initialized as a git repo during AGENTS setup; preserve git history from here onward.
- Never commit `/opt/football-club/.env`, API keys, tokens, Stripe secrets, database passwords, Docuseal secrets, or any other plaintext credentials.
- Use the active Markdown docs and approved specs as source of truth; rendered HTML companions may be stale.
- For Ansible changes, `ansible-lint`, `yamllint`, and `ansible-playbook --syntax-check` are mandatory.
- Ansible playbooks must avoid global/play-level `become`; use task-level `become: true` only for operations that require root.
- For Caddy changes, preserve existing host-owned `/etc/caddy/Caddyfile` content and limit Ansible ownership to the managed snippet file and a single ensured `import` line unless a newer approved spec says otherwise.
- For deployment changes, also run `ansible-playbook --check --diff` and apply to the Ubuntu LTS VM before claiming completion.
- Until executable restore tests exist, document and run manual validation for active-service backup and recovery paths.
- If adding code later, add exact setup/test/lint commands to this file once verified from manifests or CI.
- Prefer executable sources of truth over prose when they appear.

## Roles

- PM/Architect: keep `docs/implementation-plan.md`, scope specs, and this file aligned when repo ownership or service scope changes.
- Software Engineer: implement only against approved active deployment scope and avoid reintroducing removed-service assumptions.
- Test Engineer: keep Ansible validation and backup/recovery verification aligned with the active service set.
- Docs Writer: maintain deployment docs, operator runbooks, and current source-of-truth references.
