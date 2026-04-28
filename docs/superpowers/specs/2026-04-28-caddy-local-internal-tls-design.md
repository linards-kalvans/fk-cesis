# Caddy Local Internal TLS Design

## Context

FK CĒSIS football club platform has two deployment targets:

- **Production** — real domain with ACME TLS, subdomain routing
- **Local VM** — LAN-only access via `.lan` hostnames with Caddy internal TLS

The existing local-VM Caddy mode was path-based (`/club`, `/billing`, etc.) under a single Tailscale domain. The user requested replacing this entirely with subdomain-style `.lan` hostnames (`club.lan`, `billing.lan`, `n8n.lan`, `agreements.lan`) using Caddy's `tls internal` directive for self-signed certificates.

## Goals

- Replace path-based local-VM Caddy mode with `.lan` subdomain mode
- Keep production subdomain mode unchanged
- Ensure service URLs (Dolibarr `DOLI_URL_ROOT`, InvoiceNinja `APP_URL`, n8n `WEBHOOK_URL`) match the external access pattern for local mode
- Provide clear client-setup instructions for Linux machines (`/etc/hosts` + CA import)
- Maintain Ansible template selection via `football_club_caddy_mode` variable

## Non-Goals

- Do not change production Caddy configuration
- Do not add a configurable local TLD (hardcode `.lan`)
- Do not automate CA cert distribution to clients
- Do not support the old path mode going forward

## Design Decisions

### Decision 1: Two Caddyfile Templates

- `Caddyfile-subdomain.j2` — production, real subdomains + ACME (unchanged)
- `Caddyfile-local.j2` — local VM, `.lan` hostnames + `tls internal`

**Rationale:** Clean separation. Production keeps existing ACME flow. Local mode explicitly opts out of ACME with `tls internal` and hardcoded `.lan` names.

### Decision 2: Hardcoded `.lan` Hostnames

Local template uses fixed hostnames:
- `club.lan`
- `billing.lan`
- `n8n.lan`
- `agreements.lan`

**Rationale:** `.lan` is a stable local convention. No need for parameterization.

### Decision 3: Derived URL Variables

The `football_club_stack` role defaults compute service URLs based on `football_club_caddy_mode`:

| Variable | Local mode value | Production mode value |
|---|---|---|
| `football_club_stack_dolibarr_url_root` | `https://club.lan` | `https://club.<domain>` |
| `football_club_stack_invoiceninja_app_url` | `https://billing.lan` | `https://billing.<domain>` |
| `football_club_stack_n8n_host` | `n8n.lan` | `n8n.<domain>` |
| `football_club_stack_n8n_webhook_url` | `https://n8n.lan/` | `https://n8n.<domain>/` |

**Rationale:** Services embed their public URL in emails, redirects, and webhooks. The URL must match what clients type in their browsers.

### Decision 4: No Global `email` in Local Template

The local Caddyfile omits the `email` global option because `tls internal` does not use ACME and therefore does not need a contact email.

**Rationale:** Avoids unnecessary ACME registration attempts and keeps the local config minimal.

## Caddyfile Templates

### Local Mode (`Caddyfile-local.j2`)

```
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
}

club.lan {
  tls internal
  reverse_proxy 127.0.0.1:8081
}

billing.lan {
  tls internal
  reverse_proxy 127.0.0.1:8082
}

n8n.lan {
  tls internal
  reverse_proxy 127.0.0.1:5678
}

agreements.lan {
  tls internal
  reverse_proxy 127.0.0.1:3000
}
```

### Production Mode (`Caddyfile-subdomain.j2`) — unchanged

```
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
  email {{ football_club_admin_email }}
}

club.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:8081
}

billing.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:8082
}

n8n.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:5678
}

agreements.{{ football_club_domain }} {
  reverse_proxy 127.0.0.1:3000
}
```

## Inventory Changes

### `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`

Change:
```yaml
football_club_caddy_mode: "local"
```

All other variables remain the same. `football_club_domain` is still present for completeness but does not affect the local Caddyfile.

### `ansible/inventories/production/group_vars/production/vars.yml`

Unchanged — remains `subdomain`.

## Role Defaults Updates

### `ansible/roles/football_club_stack/defaults/main.yml`

Replace all `football_club_caddy_mode == 'path'` with `== 'local'`:

```yaml
---
football_club_stack_dolibarr_url_root: >-
  {{ 'https://club.lan' if football_club_caddy_mode == 'local' else 'https://club.' ~ football_club_domain }}

football_club_stack_invoiceninja_app_url: >-
  {{ 'https://billing.lan' if football_club_caddy_mode == 'local' else 'https://billing.' ~ football_club_domain }}

football_club_stack_n8n_host: >-
  {{ 'n8n.lan' if football_club_caddy_mode == 'local' else 'n8n.' ~ football_club_domain }}

football_club_stack_n8n_webhook_url: >-
  {{ 'https://n8n.lan/' if football_club_caddy_mode == 'local' else 'https://n8n.' ~ football_club_domain ~ '/' }}
```

## Validation Playbook Updates

### `ansible/playbooks/validate.yml`

Update the `set_fact` endpoints block:

```yaml
- name: Set service endpoint URLs
  ansible.builtin.set_fact:
    dolibarr_endpoint: >-
      {{ 'https://club.lan/' if football_club_caddy_mode == 'local'
         else 'https://club.' ~ football_club_domain ~ '/' }}
    billing_endpoint: >-
      {{ 'https://billing.lan/' if football_club_caddy_mode == 'local'
         else 'https://billing.' ~ football_club_domain ~ '/' }}
    n8n_endpoint: >-
      {{ 'https://n8n.lan/' if football_club_caddy_mode == 'local'
         else 'https://n8n.' ~ football_club_domain ~ '/' }}
    agreements_endpoint: >-
      {{ 'https://agreements.lan/' if football_club_caddy_mode == 'local'
         else 'https://agreements.' ~ football_club_domain ~ '/' }}
```

## Cleanup

- Delete `ansible/roles/caddy/templates/Caddyfile-path.j2`
- Remove all references to `path` mode in comments and documentation

## Local Client Setup Instructions

After the Ansible playbook runs on the local VM, each client Linux machine needs two steps:

### 1. Hosts file mapping

Add the VM's LAN IP and all four hostnames to `/etc/hosts`:

```bash
sudo tee -a /etc/hosts <<EOF
192.168.x.x club.lan billing.lan n8n.lan agreements.lan
EOF
```

Replace `192.168.x.x` with the actual VM IP.

### 2. Import Caddy's local CA certificate

Caddy stores its internal CA root certificate at `/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt` on the VM. Copy it to each client and install it into the system trust store:

```bash
# From client
scp user@vm:/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/caddy-local-ca.crt
sudo cp ~/caddy-local-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

After both steps, browsers and curl on the client will trust HTTPS for all four `.lan` services.

## Testing and Acceptance Criteria

1. Static checks:
   - `ansible-lint`
   - `yamllint .`
   - `ansible-playbook --syntax-check ansible/playbooks/site.yml`
2. Dry run:
   - `ansible-playbook --check --diff ansible/playbooks/site.yml`
3. Apply to local Ubuntu LTS VM:
   - Full playbook run succeeds
4. Runtime checks on the VM:
   - `docker compose -f /opt/fk-cesis/docker-compose.yml config` succeeds
   - Expected containers are running
   - `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` passes
5. Client checks:
   - `/etc/hosts` mapping resolves all four `.lan` names to VM IP
   - `curl -v https://club.lan` returns HTTP 200/302 without TLS errors after CA import
   - Same for `billing.lan`, `n8n.lan`, `agreements.lan`

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| InvoiceNinja or n8n do not fully support self-signed certificates for webhook callbacks | Medium | Test immediately after apply; if broken, investigate n8n `N8N_SKIP_WEBHOOK_DASHBOARD_RESULT_CHECK` or similar flags |
| Caddy local CA path varies by Caddy version or OS package | Low | Verify path on target VM before writing client docs; use `caddy list-modules` or check `/var/lib/caddy` |
| Client forgets to import CA and gets browser warnings | High | Document the two-step client setup prominently in runbook |

## Documentation Updates Required

- Update `docs/implementation-plan.md` Phase 1 Caddy configuration section to describe local `.lan` mode instead of path mode
- Add local client setup instructions to a new or existing runbook
- Update `AGENTS.md` if it references path-based Caddy mode

## Approval State

Design approved 2026-04-28.
