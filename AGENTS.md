# Project Overview

Self-hosted hybrid platform plan for football club FK CĒSIS. Current repo is documentation-only; no application code, manifests, CI, or executable test tooling exists yet.

## Scope

- Build/operate club admin stack described in `docs/implementation-plan.md`.
- Dolibarr is system of record for members, teams, events, attendance, and documents.
- InvoiceNinja is system of record for billing, payments, clients, vendors, and expenses.
- n8n is integration/event bus; keep Dolibarr and InvoiceNinja decoupled.
- Integrations must use REST APIs and webhooks only; do not plan direct DB coupling between services.

## Milestones

- Phase 1: deploy core services, import roster, verify Stripe Latvia SEPA/card, backups.
- Phase 2: configure recurring billing MVP; 5 pilot members complete one payment cycle.
- Phase 3: automate attendance polling and coach billing through n8n/WhatsApp.
- Phase 4: automate registration, OCR prefill, Docuseal signing, and member activation.
- Phase 5: full rollout, monitoring, treasurer/ops handover runbooks.

## Specs

- Approved design specs live under `docs/superpowers/specs/`.
- Current deployment foundation spec: `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`.
- Treat `docs/implementation-plan.md` as current source of truth for architecture, risks, env vars, and acceptance gates until a more specific approved spec or plan applies.
- `docs/html/implementation-plan.html` is a rendered companion and may be stale; update Markdown first if content changes, and only regenerate HTML when explicitly in scope.

## Plans

- Primary plan: `docs/implementation-plan.md`.
- Deployment foundation planning must follow `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md` until a detailed implementation plan supersedes it.
- Do not add implementation details that conflict with this plan unless the plan is updated in the same change.
- Phase gates in the plan are hard stops; especially verify real Stripe Latvia SEPA/card support before moving past Phase 1.

## Tech Stack

- Dolibarr: `dolibarr/dolibarr:latest` with MariaDB.
- InvoiceNinja: `invoiceninja/invoiceninja-octane:latest` with MariaDB.
- n8n: `n8nio/n8n:latest` with PostgreSQL.
- Docuseal: `docuseal/docuseal:latest` with SQLite volume.
- DocTR OCR: `ghcr.io/mindee/doctr:api-cpu-latest`, intended on-demand unless host RAM allows always-on.
- Stripe: external payment gateway for card and SEPA in Latvia.
- Caddy: existing reverse proxy and TLS termination.
- Grafana Alloy and UptimeRobot are planned monitoring pieces in Phase 5.
- Ansible is the deployment automation tool for the Phase 1 foundation.
- Docker Compose remains the runtime orchestrator.
- Ansible Vault is required for committed encrypted secrets.

## Workflow Rules

- This repo was initialized as a git repo during AGENTS setup; preserve git history from here onward.
- Never commit `/opt/football-club/.env`, API keys, tokens, Stripe secrets, WhatsApp tokens, database passwords, or real ID document photos.
- Until executable tests exist, use the phase acceptance tests in `docs/implementation-plan.md` as verification checklists.
- For Ansible changes, `ansible-lint`, `yamllint`, and `ansible-playbook --syntax-check` are mandatory.
- Ansible playbooks must avoid global/play-level `become`; use task-level `become: true` only for operations that require root.
- For deployment changes, also run `ansible-playbook --check --diff` and apply to the Ubuntu LTS VM before claiming completion.
- If adding code later, add exact setup/test/lint commands to this file once verified from manifests or CI.
- Prefer executable sources of truth over prose when they appear; currently no executable sources exist.

## Roles

- PM/Architect: keep `docs/implementation-plan.md` and this file aligned when scope, architecture, or workflow changes.
- Software Engineer: implement only against approved phase scope and preserve REST/webhook boundaries.
- Test Engineer: convert phase acceptance tests into executable or manual verification steps before implementation where possible.
- Docs Writer: maintain `docs/implementation-plan.md`, future runbooks (`TREASURER.md`, `OPS.md`), and rendered HTML companion if used.
