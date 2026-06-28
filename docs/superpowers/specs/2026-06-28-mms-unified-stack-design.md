# MMS Unified Stack Design

## Status

Approved for implementation planning.

## Problem

FK Cēsis MMS currently has a standalone manual runtime under `deploy/fk-cesis-mms/` and `docs/fk-cesis-mms-deployment.md`. That separates MMS from the Ansible-managed Compose stack that already runs InvoiceNinja and Docuseal.

MMS needs direct integration with InvoiceNinja and Docuseal. Keeping it in a separate Compose project adds avoidable routing, secret, backup, and deployment drift.

## Goals

- Add MMS to the existing Ansible-managed Docker Compose stack.
- Keep MMS, InvoiceNinja, and Docuseal on the same Compose network.
- Let MMS call InvoiceNinja and Docuseal over internal Docker service URLs.
- Serve MMS through Caddy at the `members` hostname.
- Manage MMS configuration and secrets through Ansible and Ansible Vault.
- Include MMS data in backup and validation workflows.

## Non-goals

- Do not change MMS application code.
- Do not automatically create InvoiceNinja or Docuseal API keys.
- Do not migrate existing standalone MMS data into the unified stack.
- Do not apply the production deployment during this change.

## Architecture

MMS becomes part of the existing `football_club_stack` role. The Docker Compose template will define:

- `mms-postgres` for the MMS database.
- `mms-web` for the Django web process.
- `mms-qcluster` for background jobs.

The services will use the default Compose network. No external Docker network is needed.

```text
Caddy
  ├─ billing.<domain>    -> 127.0.0.1:8089 -> nginx -> InvoiceNinja
  ├─ agreements.<domain> -> 127.0.0.1:3039 -> Docuseal
  └─ members.<domain>    -> 127.0.0.1:8000 -> MMS web

mms-web / mms-qcluster
  ├─ DATABASE_URL         -> postgres://...@mms-postgres:5432/...
  ├─ INVOICE_NINJA_API_URL -> http://nginx
  └─ DOCUSEAL_API_URL      -> http://docuseal:3000
```

## Routing

Caddy keeps the current ownership model: Ansible manages only the imported FK Cēsis snippet and the import line in the host-owned main Caddyfile.

Subdomain mode:

- `members.<domain>` proxies to `127.0.0.1:8000`.

Local mode:

- `members.lan` proxies to `127.0.0.1:8000`.
- `members.lan` uses `tls internal` like the other local routes.

## Configuration

Add normal Ansible variables for MMS runtime settings:

- `football_club_stack_mms_image`
- `football_club_stack_mms_image_tag`
- `football_club_stack_mms_site_url`
- `football_club_stack_mms_allowed_hosts`

Image tag defaults:

- local VM inventory uses `dev`.
- production inventory uses `main`.

MMS provider modes are live by default:

- `AGREEMENT_PROVIDER_MODE=docuseal`
- `INVOICE_PROVIDER_MODE=invoiceninja`

Internal integration URLs:

- `DOCUSEAL_API_URL=http://docuseal:3000`
- `INVOICE_NINJA_API_URL=http://nginx`

## Secrets

MMS secrets must be rendered from Ansible Vault into the shared stack `.env`. Vault examples should include placeholder values for:

- Django secret key.
- MMS Postgres password.
- OCR encryption key.
- OCR API key if used.
- Docuseal API key.
- Docuseal template ID.
- Docuseal webhook secret.
- InvoiceNinja API key.
- SMTP password.
- Django superuser bootstrap password.

No plaintext live secret may be committed.

## Backup

The backup script will include active MMS persistent data:

- MMS Postgres dump.
- MMS uploads data.
- MMS private uploads data.

Existing backup coverage for InvoiceNinja and Docuseal remains unchanged.

## Validation

The validation playbook will check the MMS endpoint in addition to existing services:

- subdomain mode: `https://members.<domain>/healthz`
- local mode: `https://members.lan/healthz`

The endpoint must return a successful status accepted by the playbook.

## Documentation

Update documentation so the unified Ansible stack is the MMS deployment source of truth.

Required docs updates:

- `docs/fk-cesis-mms-deployment.md` marks standalone deployment as legacy/manual and points operators to the Ansible stack.
- `ansible/README.md` includes the `members` DNS entry, MMS secret placeholders, validation expectations, and backup scope.
- `docs/implementation-plan.md` and `AGENTS.md` reflect MMS as active deployment scope after implementation.

## Acceptance criteria

- Unified Compose contains MMS web, qcluster, and Postgres services.
- MMS services share the Compose network with InvoiceNinja and Docuseal.
- MMS uses `http://nginx` for InvoiceNinja and `http://docuseal:3000` for Docuseal.
- Caddy serves `members.<domain>` and `members.lan`.
- Ansible Vault examples include MMS secret placeholders.
- Backup script covers MMS database and upload data.
- Validation checks the MMS `/healthz` endpoint.
- Standalone MMS docs no longer present the custom directory as the primary deployment path.
- Required Ansible lint and syntax checks pass during implementation verification.
