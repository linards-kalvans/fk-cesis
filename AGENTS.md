# Project Overview

Ansible deployment and operations documentation repo for FK CĒSIS. The repo is used to keep the club environment repeatable across local VM and future production-style hosts. Application/product development for the future in-house member management system will happen in a separate project; FK Cēsis MMS deployment integration is in scope here.

## Scope

- Maintain repeatable Ansible deployment for InvoiceNinja, Docuseal, FK Cēsis MMS, optional Caddy, and deployment recovery checkpoints. The legacy backup role is retained, but routine daily-backup work is deferred to the separate `server-backups` project.
- Keep deployment docs, operator workflows, and secret-handling guidance aligned with the active stack.
- Keep FK Cēsis MMS deployment integrated in the active Ansible stack; application development remains in the separate MMS project.
- Do not treat Dolibarr, n8n, or DocTR as current-scope services in this repository.

## Milestones

- Milestone 1: narrow source-of-truth docs to the active deployment scope.
- Milestone 2: keep local VM and production-style deployment repeatable for InvoiceNinja, Docuseal, FK Cēsis MMS, Caddy, and deployment recovery checkpoints; coordinate routine daily backups with `server-backups`.
- Milestone 3: document validated operator workflows for secrets, deploy, smoke checks, and recovery.
- Milestone 4: add the future in-house member management system only after a separate approved spec and plan exist; keep FK Cēsis MMS deployment integrated in the meantime.

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
- InvoiceNinja: Debian-based PHP-FPM image with MariaDB; the active VM and production inventories select separately verified host-native PHP-hotpatch image IDs. The role's Debian `latest` reference is only an unverified fallback, not the production selection. See `docs/invoiceninja-php-security-hotpatch.md`.
- Docuseal: `docuseal/docuseal:latest` with SQLite volume.
- FK Cēsis MMS: image repository and tag come from the active stack role defaults and inventory overrides, with PostgreSQL. Do not copy historical Codeberg references over the current configuration.
- Caddy provides reverse proxy and TLS termination.
- Ansible-managed club routes should live in a dedicated Caddy snippet imported from the host's main Caddyfile, not by replacing the whole main file.
- Ansible Vault is required for committed encrypted secrets.
- The retained legacy backup role covers active service data and databases only; routine daily backup ownership is `server-backups`.

## Workflow Rules

- This repo was initialized as a git repo during AGENTS setup; preserve git history from here onward.
- Never commit `/opt/football-club/.env`, API keys, tokens, Stripe secrets, database passwords, Docuseal secrets, or any other plaintext credentials.
- Use the active Markdown docs and approved specs as source of truth; rendered HTML companions may be stale.
- For Ansible changes, `ansible-lint`, `yamllint`, and `ansible-playbook --syntax-check` are mandatory.
- Ansible playbooks must avoid global/play-level `become`; use task-level `become: true` only for operations that require root.
- For Caddy changes, preserve existing host-owned `/etc/caddy/Caddyfile` content and limit Ansible ownership to the managed snippet file and a single ensured `import` line unless a newer approved spec says otherwise.
- For deployment changes, also run `ansible-playbook --check --diff` and apply to the Ubuntu LTS VM before claiming completion.
- Until executable restore tests exist, document and run manual validation for active-service backup and recovery paths.
- Per user direction (2026-10-29), defer routine daily/offsite backup remediation to `server-backups`. Keep one-off deployment checkpoints and recovery gates here. Do not infer server-wide backup coverage from the legacy `backup.sh` findings, or remove/disable its role or cron without a separately approved change.
- If adding code later, add exact setup/test/lint commands to this file once verified from manifests or CI.
- Prefer executable sources of truth over prose when they appear.
- Security maintenance and remaining release blockers: `docs/deployment-security-review.md`. Ordinary stack startup uses `--pull never`; preload reviewed images before first deployment. MMS refresh requires explicit `football_club_stack_pull_mms_images=true` and approval for any production change.
- Invoice Ninja proxy boundary and local smoke procedure: `docs/invoiceninja-proxy-hardening.md`. nginx normalizes host-Caddy forwarding using its own bridge gateway and strips forwarded headers before PHP; Laravel trusts loopback only. Verify the host-ingress assumptions on the VM before rollout; do not widen trust to a shared subnet.
- Secret-free security checks (system Python with Jinja2/PyYAML): `/usr/bin/python3 -m unittest discover -s tests -p test_deployment_security.py -v` and `/usr/bin/python3 -m unittest discover -s tests -p test_invoiceninja_vm_hotpatch.py -v`. The first also requires Docker Compose, but does not contact its daemon or start containers.
- From `ansible/`: `ansible-lint roles playbooks tests`, `yamllint .`, `ansible-playbook --syntax-check playbooks/site.yml`, and `ansible-playbook --syntax-check playbooks/validate.yml`. Do not decrypt Vault files for CI.

## Roles

- PM/Architect: keep `docs/implementation-plan.md`, scope specs, and this file aligned when repo ownership or service scope changes.
- Software Engineer: implement only against approved active deployment scope and avoid reintroducing removed-service assumptions.
- Test Engineer: keep Ansible validation and backup/recovery verification aligned with the active service set.
- Docs Writer: maintain deployment docs, operator runbooks, and current source-of-truth references.
