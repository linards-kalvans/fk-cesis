# Caddy Imported Snippet Design

## Context

FK CĒSIS currently deploys Caddy through the Ansible `caddy` role. The existing role renders a full template directly to `/etc/caddy/Caddyfile`, which replaces whatever configuration the host already has.

That behavior conflicts with the current operational need. The host's main Caddyfile may contain pre-existing global options, unrelated sites, or machine-specific configuration that should remain host-owned. The FK CĒSIS Ansible repo only needs to add and maintain the club routes for the active services it owns.

## Problem

The current Caddy role takes ownership of the entire `/etc/caddy/Caddyfile`. That creates three risks:

- existing host-managed or manually curated Caddy configuration is lost on deploy;
- Ansible changes for FK CĒSIS cannot safely coexist with other Caddy workloads on the same machine;
- validation of the deployed Caddy configuration does not reflect the intended ownership boundary between the repo and the host.

## Goals

- Preserve the host-owned main `/etc/caddy/Caddyfile`.
- Let Ansible manage only FK CĒSIS route definitions for the active services.
- Keep the current routing-mode split between `subdomain` and `local`.
- Make repeated playbook runs idempotent.
- Validate the effective Caddy configuration that Caddy actually loads.

## Non-Goals

- Do not redesign routing mode semantics.
- Do not reintroduce Dolibarr, n8n, or DocTR.
- Do not manage unrelated host Caddy sites from this repository.
- Do not require a full rewrite of the host's existing Caddy layout.

## Recommended Approach

Manage a dedicated snippet file for FK CĒSIS routes and ensure the host's main Caddyfile imports it.

The role should render a managed snippet file under `/etc/caddy/`, for example `/etc/caddy/football-club-routes.caddy`, from the existing routing-mode templates. The main `/etc/caddy/Caddyfile` stays host-owned, except that Ansible ensures exactly one `import` line exists for the managed snippet.

This is preferred over in-place block editing of the full Caddyfile because it keeps the Ansible-owned surface area narrow, easier to reason about, and less sensitive to surrounding formatting or host-specific edits.

Alternatives considered:

1. Replace the whole main Caddyfile. Rejected because it breaks the required ownership boundary.
2. Insert a marked managed block directly into the main Caddyfile. Rejected because it is more fragile when host-owned content changes around the block.

## Architecture

### Managed Files

The Caddy role should manage:

- the FK CĒSIS snippet file containing club routes;
- a single ensured `import` statement in the main Caddyfile;
- the first-takeover backup of the main Caddyfile before Ansible adds the import.

The role should no longer template the entire main Caddyfile.

### Template Ownership

The existing route templates remain the source of truth for FK CĒSIS route blocks:

- `ansible/roles/caddy/templates/Caddyfile-subdomain.j2`
- `ansible/roles/caddy/templates/Caddyfile-local.j2`

They should render only the club route definitions needed by FK CĒSIS. Global options should live in the host-owned main Caddyfile, not in the managed snippet.

### Import Strategy

The main Caddyfile should contain exactly one line that imports the managed snippet. The Ansible role should ensure that line exists without overwriting the rest of the file.

If the main Caddyfile does not exist, the role may create a minimal host-compatible file that contains the import line, but the primary design assumption is preservation of an existing host file.

### Validation Model

Validation should run against the main Caddyfile path, because that is the effective configuration entrypoint. A successful validation proves that the host-owned content and the Ansible-managed snippet compose correctly.

## Testing and Acceptance Criteria

Mandatory repo validation for this change remains:

- `ansible-lint`
- `yamllint .`
- `ansible-playbook --syntax-check`
- `ansible-playbook --check --diff`

Behavioral acceptance criteria:

- Ansible no longer overwrites `/etc/caddy/Caddyfile` on normal runs.
- Ansible renders a dedicated FK CĒSIS snippet file under `/etc/caddy/`.
- The main Caddyfile contains exactly one import of that snippet after apply.
- Re-running the role is idempotent.
- `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` passes with the import-based structure.
- Existing host-owned content outside the ensured import line remains intact.

## Documentation Updates Required

- Update `AGENTS.md` to record the Caddy ownership boundary.
- Update current source-of-truth deployment docs and plans that still say Ansible owns the full main Caddyfile.
- Keep historical routing-mode specs as history only; do not reinterpret them as full-file ownership guidance.

## Approval State

Approved by the user on 2026-05-07:

- Ansible should manage a separate Caddy snippet file;
- the remote host's main Caddyfile should be preserved and only augmented with an `import`.
