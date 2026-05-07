# Ansible Scope Reduction Design

## Context

FK CĒSIS decided not to use Dolibarr for member management. The club will build an in-house member management system in a separate project. This repository should now focus on repeatable infrastructure automation and operator documentation for the currently needed services only.

The repository already contains Ansible automation, deployment docs, and planning artifacts that still describe a broader club platform with Dolibarr, n8n, and DocTR in active scope. Those references now make the repo inaccurate and harder to operate.

## Problem

The current documentation overstates what this repository owns. It still presents the repo as the source of truth for a multi-service club operations platform instead of an Ansible deployment repo for a narrower environment. That mismatch creates three concrete problems:

- operators may provision or validate services that are no longer wanted;
- project guidance still treats removed services as required milestones and acceptance gates;
- future work on the in-house member system has no clean boundary because the current docs imply the old Dolibarr-centered architecture is still active.

## Goals

- Reframe this repository as an Ansible deployment and operations documentation repo.
- Keep active scope limited to InvoiceNinja, Docuseal, Caddy, and backup automation.
- Remove Dolibarr, n8n, and DocTR from current scope, architecture, milestones, and validation guidance.
- Preserve a clear extension point for adding the future in-house member management system later.
- Keep Ansible Vault, repeatable deployment, and deployment validation as core workflow requirements.

## Non-Goals

- Do not design the in-house member management system in this repository.
- Do not add the future member system to the playbook yet.
- Do not keep speculative workflow automation for attendance, OCR, WhatsApp, or integration bus features in current-scope docs.
- Do not regenerate `docs/html/implementation-plan.html` unless explicitly requested.

## Recommended Approach

Repurpose this repository into a deployment-focused source of truth. The repo should describe only the infrastructure and operational concerns it currently owns: host provisioning, Docker Compose runtime, Caddy ingress, InvoiceNinja, Docuseal, secret management, validation, and backups.

The future in-house member management system should be mentioned only as a later integration target. It should not be given current architecture details, endpoints, or acceptance criteria until a separate approved spec exists.

Alternatives considered:

1. Keep the broader platform framing and mark some services deferred. Rejected because it preserves ambiguity about current ownership.
2. Keep current docs as historical artifacts and add a short note about the change. Rejected because the current docs are still referenced as active source of truth.
3. Split the repo immediately into active and speculative future platform sections. Partially useful, but only a short future note is needed now.

## Architecture

### Current Managed Runtime

This repository currently manages and documents deployment for:

- InvoiceNinja for billing and payment operations;
- Docuseal for document signing workflows;
- Caddy for ingress and TLS termination;
- backup automation for persistent service data and database dumps.

### Removed Current-Scope Services

These services are no longer part of the current repository scope:

- Dolibarr;
- n8n;
- DocTR OCR.

Any references to those services in current source-of-truth documents should be removed or rewritten unless the document is explicitly historical.

### Future Extension Point

A future in-house member management system may later be deployed by the same Ansible stack. Until that system has its own approved design and implementation plan, the repo should only reserve architectural room for an additional service behind Caddy and associated backup/secret handling requirements.

No assumptions should be documented yet about its language, API shape, database, or hostname.

## Milestones

Replace the previous platform phases with deployment-focused milestones:

1. Narrow the repo scope and source-of-truth docs to the active service set.
2. Maintain a repeatable Ansible deployment for InvoiceNinja, Docuseal, Caddy, and backups across local VM and production-style hosts.
3. Document operator workflows for secrets, deploy, validate, and recovery.
4. Prepare the repo structure to accept the future in-house member management system without reintroducing removed-service assumptions.

## Testing and Acceptance Criteria

For documentation and Ansible-scope updates, verification should focus on the active service set only.

Mandatory checks remain:

- `ansible-lint`
- `yamllint .`
- `ansible-playbook --syntax-check`
- `ansible-playbook --check --diff`

Deployment validation should confirm only the active endpoints and services that the playbooks currently manage. Backup expectations should cover only active persistent data.

Current-scope documentation should no longer require validation or smoke checks for Dolibarr, n8n, or DocTR.

## Documentation Updates Required

Update these active source-of-truth documents:

- `AGENTS.md`
- `docs/implementation-plan.md`
- `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md`
- `ansible/README.md`

Also update directly referenced current documentation and guidance where it still describes removed services as active scope.

Historical plans and specs may remain in the repo, but they must not be presented as the current source of truth if they conflict with the narrowed scope.

## Approval State

Approved by the user on 2026-05-04:

- this repo owns Ansible automation and docs for InvoiceNinja, Docuseal, Caddy, and backups;
- DocTR and n8n are out of scope for now;
- the future in-house member management system may be added later.
