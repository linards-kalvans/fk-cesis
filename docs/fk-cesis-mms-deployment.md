# FK Cēsis MMS Deployment

## Current source of truth

FK Cēsis MMS is deployed by the unified Ansible stack in `ansible/`.

The active runtime is part of the same Docker Compose project as InvoiceNinja and Docuseal so MMS can call them over the internal Docker network:

- InvoiceNinja: `http://nginx`
- Docuseal: `http://docuseal:3000`

Ingress is handled by Caddy:

- Production-style: `https://members.<domain>`
- Local VM: `https://members.lan`

The MMS web container binds to `127.0.0.1:8019` on the host by default (configurable via `football_club_stack_mms_host_port`). When `football_club_manage_caddy` is `false`, the Caddy route is managed outside this repo.

Use `ansible/README.md` for operator setup, secrets, validation, and backup workflow.

## Legacy manual runtime

The standalone files under `deploy/fk-cesis-mms/` are retained only as legacy/manual reference material. They are not the primary deployment path for this repository.

Do not deploy new FK Cēsis MMS environments from `/opt/fk-cesis-mms` unless a future approved spec restores that mode.

## Secrets rule

Never commit real `.env` values, deploy webhook secrets, API keys, SMTP passwords, OCR keys, Docuseal keys, InvoiceNinja keys, database passwords, or Django secrets.
