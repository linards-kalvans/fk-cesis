# Caddy Routing Modes — Path-Based vs Subdomain Design

> Date: 2026-04-27
> Status: Draft

---

## Problem Statement

The current Ansible deployment only supports subdomain-based reverse proxy routing (e.g. `club.example.lv`, `billing.example.lv`). The target Ubuntu LTS VM is accessible only via a Tailscale subdomain (`skuby7.tail45ce0a.ts.net`) with no wildcard DNS capability. We need path-based routing (`/club`, `/billing`, `/n8n`, `/agreements`) for local VM testing while keeping the existing subdomain approach for production.

---

## Goals

1. Support **path-based reverse proxy routing** under a single domain for local VM / Tailscale access.
2. Preserve **existing subdomain-based routing** for production deployments.
3. Keep service containers **routing-mode agnostic** — no container-level changes between environments.
4. Control the routing mode entirely through **Ansible inventory variables**.
5. Ensure all services generate correct self-referential URLs (redirects, emails, webhooks) in both modes.
6. Make Caddy listener ports configurable per environment via Ansible variables.

---

## Non-Goals

- Changing the underlying Docker Compose service topology.
- Adding new services beyond the existing four (Dolibarr, InvoiceNinja, n8n, Docuseal).
- TLS certificate management logic — Caddy handles this automatically.
- Load balancing or high availability.

---

## Design Decisions

### Decision 1: Separate Caddyfile Templates

**Rationale:** The user explicitly requested separate templates. A single template with heavy Jinja2 conditionals would be harder to read and validate. Two self-contained templates are easier to review, test, and lint independently.

- `Caddyfile-subdomain.j2` — subdomain routing, one site block per service.
- `Caddyfile-path.j2` — path routing, one site block with `handle_path` matchers.

### Decision 2: `handle_path` for Prefix Stripping

**Rationale:** Caddy's `handle_path` directive strips the matched path prefix before proxying. This means Dolibarr receives `/login` instead of `/club/login`, eliminating the need for complex app-level base URL reconfiguration in most cases. InvoiceNinja and n8n still need their `APP_URL` / `WEBHOOK_URL` environment variables updated to generate correct links, but the proxy layer remains transparent.

### Decision 3: Service URLs Rendered from Template Variables

**Rationale:** Services like InvoiceNinja embed their public URL in invoice emails and PDFs. If the `APP_URL` does not match the external access pattern, links break. We introduce derived variables (`dolibarr_url_root`, `invoiceninja_app_url`, etc.) that the docker-compose template consumes, computed from `football_club_domain` and `football_club_caddy_mode`.

### Decision 4: Inventory-Driven Mode Selection

**Rationale:** The `local_vm` and `production` inventories already separate environments. Adding `football_club_caddy_mode` to each inventory's `vars.yml` is the natural place. No host-level conditionals are needed in roles.

---

## Caddyfile Templates

### Subdomain Mode (`Caddyfile-subdomain.j2`)

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

### Path Mode (`Caddyfile-path.j2`)

```
{
  http_port {{ football_club_caddy_http_port }}
  https_port {{ football_club_caddy_https_port }}
  email {{ football_club_admin_email }}
}

{{ football_club_domain }} {
  handle_path /club/* {
    reverse_proxy 127.0.0.1:8081
  }

  handle_path /billing/* {
    reverse_proxy 127.0.0.1:8082
  }

  handle_path /n8n/* {
    reverse_proxy 127.0.0.1:5678
  }

  handle_path /agreements/* {
    reverse_proxy 127.0.0.1:3000
  }

  handle {
    redir /club/
  }
}
```

---

## Docker Compose Template Changes

The following environment variables must derive from Ansible vars instead of being hardcoded:

| Variable | Current Hardcoded | New Template Expression |
|---|---|---|
| `DOLI_URL_ROOT` | `https://club.${DOMAIN}` | `{{ dolibarr_url_root }}` |
| `APP_URL` (InvoiceNinja) | `https://billing.${DOMAIN}` | `{{ invoiceninja_app_url }}` |
| `N8N_HOST` | `n8n.${DOMAIN}` | `{{ n8n_host }}` |
| `WEBHOOK_URL` | `https://n8n.${DOMAIN}/` | `{{ n8n_webhook_url }}` |

Derived variables are computed in the `football_club_stack` role defaults (`ansible/roles/football_club_stack/defaults/main.yml`) based on `football_club_caddy_mode`, making them available to the docker-compose template without duplication in every inventory.

**Subdomain mode values:**
- `dolibarr_url_root`: `https://club.{{ football_club_domain }}`
- `invoiceninja_app_url`: `https://billing.{{ football_club_domain }}`
- `n8n_host`: `n8n.{{ football_club_domain }}`
- `n8n_webhook_url`: `https://n8n.{{ football_club_domain }}/`

**Path mode values:**
- `dolibarr_url_root`: `https://{{ football_club_domain }}/club`
- `invoiceninja_app_url`: `https://{{ football_club_domain }}/billing`
- `n8n_host`: `{{ football_club_domain }}`
- `n8n_webhook_url`: `https://{{ football_club_domain }}/n8n/`

> Note: Docuseal may require additional `HOST` or `BASE_URL` configuration if it generates self-referential links. This is left as a post-implementation verification step; the container currently has no such variable.

---

## Ansible Variable Additions

Added to **both** `inventories/local_vm/group_vars/local_vm/vars.yml` and `inventories/production/group_vars/production/vars.yml`:

```yaml
# Routing mode: "subdomain" or "path"
football_club_caddy_mode: "subdomain"

# Caddy listener ports
football_club_caddy_http_port: 80
football_club_caddy_https_port: 443
```

**Local VM specific values:**
```yaml
football_club_domain: "skuby7.tail45ce0a.ts.net"
football_club_caddy_mode: "path"
football_club_caddy_http_port: 80
football_club_caddy_https_port: 443
```

**Production specific values:**
```yaml
football_club_domain: "example.lv"
football_club_caddy_mode: "subdomain"
football_club_caddy_http_port: 80
football_club_caddy_https_port: 443
```

---

## Caddy Role Changes

The caddy role's `main.yml` is updated to select the template source dynamically:

```yaml
- name: Render managed Caddyfile
  ansible.builtin.template:
    src: "Caddyfile-{{ football_club_caddy_mode }}.j2"
    dest: "{{ football_club_caddyfile_path }}"
    ...
```

Both `Caddyfile-subdomain.j2` and `Caddyfile-path.j2` are placed in `ansible/roles/caddy/templates/`.

The old `Caddyfile.j2` is removed to prevent ambiguity.

---

## Validation Playbook Changes

`ansible/playbooks/validate.yml` currently hardcodes subdomain URLs. It must instead construct URLs based on `football_club_caddy_mode`:

- **Subdomain mode:** keep existing `https://club.{{ domain }}`, `https://billing.{{ domain }}`, etc.
- **Path mode:** use `https://{{ domain }}/club`, `https://{{ domain }}/billing`, etc.

This can be achieved by setting service endpoint facts in a pre-task or by using `set_fact` with `football_club_caddy_mode` conditionals.

---

## Testing Strategy

1. **Static analysis:**
   - `ansible-lint` passes
   - `yamllint .` passes
   - `ansible-playbook --syntax-check` passes for both inventories

2. **Dry-run verification:**
   - `ansible-playbook --check --diff` against local VM shows correct template selection and variable rendering

3. **Caddy config validation:**
   - `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` passes after apply

4. **Smoke tests:**
   - `curl -sf https://skuby7.tail45ce0a.ts.net/club/` returns 200/302
   - `curl -sf https://skuby7.tail45ce0a.ts.net/billing/` returns 200/302
   - `curl -sf https://skuby7.tail45ce0a.ts.net/n8n/` returns 200/302
   - `curl -sf https://skuby7.tail45ce0a.ts.net/agreements/` returns 200/302
   - Root path redirects to `/club/`

5. **App URL consistency:**
   - Dolibarr admin panel login form action URL points to `/club/` path
   - InvoiceNinja generated invoice PDF contains correct domain/path

---

## Acceptance Criteria

- [ ] `local_vm` inventory renders `Caddyfile-path.j2` with `skuby7.tail45ce0a.ts.net` as the single domain.
- [ ] `production` inventory renders `Caddyfile-subdomain.j2` with `example.lv` base domain.
- [ ] Docker Compose template renders correct `DOLI_URL_ROOT`, `APP_URL`, `N8N_HOST`, and `WEBHOOK_URL` for each mode.
- [ ] Caddy role selects template based on `football_club_caddy_mode` variable.
- [ ] Old `Caddyfile.j2` is removed from repository.
- [ ] Validation playbook constructs correct URLs for both routing modes.
- [ ] All Ansible lint and syntax checks pass.
- [ ] Local VM smoke tests pass after apply.
- [ ] Production variable files remain compatible with existing subdomain deployment.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| InvoiceNinja or n8n do not fully support subpath deployment | Medium | Test immediately after apply; if broken, fallback to subdomain mode with `/etc/hosts` workaround on local machine. |
| Docuseal link generation breaks under path mode | Low | Docuseal is mainly webhook-driven; verify signing links work after deployment. |
| Tailscale DNS latency or caching causes cert issues | Low | Caddy's Tailscale integration handles certificates internally; verify with `caddy adapt`. |

---

## Related Documents

- `docs/implementation-plan.md` — Phase 1 Caddy configuration section
- `docs/superpowers/specs/2026-04-26-ansible-deployment-foundation-design.md` — Deployment foundation spec
