# FK CĒSIS Ansible Deployment

This directory deploys the current FK CĒSIS environment foundation: InvoiceNinja, Docuseal, Caddy, and backup automation.

## Requirements

Control machine:

- Ansible
- ansible-lint
- yamllint

Install collections:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

## Local VM setup

### 1. Inventory — set VM IP, user, and optional SSH key

Edit `ansible/inventories/local_vm/hosts.yml`. The defaults below use an RFC 5737 documentation address; replace with your real values.

```yaml
---
all:
  children:
    local_vm:
      children:
        football_club:
          hosts:
            local-vm:
              ansible_host: 192.0.2.10
              ansible_user: ubuntu
#              ansible_ssh_private_key_file: ~/.ssh/id_ed25519
```

**Quick SSH test**:

```bash
ssh ubuntu@192.0.2.10 "echo OK"
```

A successful login confirms Ansible can reach the host.

### 2. Group vars — set domain and admin email

Edit `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`.

```yaml
football_club_domain: "example.lv"
football_club_admin_email: "admin@example.lv"
```

### 3. DNS names to point at the VM IP

For `subdomain` mode, create A records for the active public endpoints:

| Subdomain | Served by |
|---|---|
| `billing.<domain>` | InvoiceNinja |
| `agreements.<domain>` | Docuseal |

Example for `example.lv`:

```text
billing.example.lv    -> 192.0.2.10
agreements.example.lv -> 192.0.2.10
```

For `local` mode (`.lan` hostnames with internal TLS), add host entries on every client machine that will access the VM, then import Caddy's root CA certificate so browsers trust the self-signed HTTPS.

**a) `/etc/hosts` mapping**:

```bash
sudo tee -a /etc/hosts <<'HOSTS_EOF'
192.168.x.x billing.lan agreements.lan
HOSTS_EOF
```

Replace `192.168.x.x` with the actual VM LAN IP.

**b) Import Caddy's internal CA certificate**:

```bash
scp ubuntu@192.168.x.x:/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/caddy-local-ca.crt
sudo cp ~/caddy-local-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

### 4. Encrypted vault — secrets never committed

**Step A — create a local staging copy:**

```bash
cp ansible/inventories/local_vm/group_vars/local_vm/vault.example.yml /tmp/local-vault.yml
```

Edit `/tmp/local-vault.yml` with real or test values.

**Step B — encrypt to the tracked location:**

```bash
ansible-vault encrypt --output ansible/inventories/local_vm/group_vars/local_vm/vault.yml   /tmp/local-vault.yml
```

Delete the plaintext staging file after verifying the encrypted output:

```bash
rm -f /tmp/local-vault.yml
```

**Step C — edit later:**

```bash
ansible-vault edit ansible/inventories/local_vm/group_vars/local_vm/vault.yml
```

### 5. Secret values for local VM testing

For local testing, use non-production credentials only.

Generate random values for database passwords, encryption keys, and application secrets:

```bash
openssl rand -base64 32
openssl rand -base64 64
```

Never commit live secrets or plaintext vault contents.

## Retry / dry-run

After every Ansible change, before applying:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff   ansible/playbooks/site.yml --ask-vault-pass
```

If the dry run succeeds, apply the playbook to the local VM.

### Volume ownership note

InvoiceNinja requires writable persistent storage for Laravel cache, sessions, views, and logs. Keep volume ownership and write-permission behavior aligned with the running container image and verify it in the stack role.

## Required checks

Run every time Ansible changes:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-lint ansible/playbooks/site.yml ansible/playbooks/validate.yml
yamllint .
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/site.yml
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --syntax-check ansible/playbooks/validate.yml
```

Run before applying:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff ansible/playbooks/site.yml --ask-vault-pass
```

Apply to local VM:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/site.yml --ask-vault-pass
```

Validate deployment:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook ansible/playbooks/validate.yml --ask-vault-pass
```

## Validation expectations

Validation should cover only the active service set:

- InvoiceNinja endpoint (`billing`)
- Docuseal endpoint (`agreements`)
- Compose configuration renders successfully
- Caddy validates and reloads successfully
- backup workflow covers active persistent data only

## Caddy ownership model

The host-owned `/etc/caddy/Caddyfile` remains the main Caddy entrypoint. This repo renders FK CĒSIS routes to a dedicated snippet file and ensures the main file imports it.

Managed by the playbook:

- `/etc/caddy/football-club-routes.caddy`
- one `import /etc/caddy/football-club-routes.caddy` line in `/etc/caddy/Caddyfile`

Not replaced by the playbook during normal runs:

- unrelated host-owned Caddy global options
- unrelated host-owned site blocks already present in `/etc/caddy/Caddyfile`

If the active playbook still contains legacy services during transition, do not treat them as required success criteria for this repo's current scope.

## Secret rules

Never commit plaintext secrets, vault passwords, generated `.env` files, API tokens, database passwords, Stripe secrets, Docuseal secrets, or any other live credentials.
