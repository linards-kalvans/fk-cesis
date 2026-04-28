# FK CĒSIS Ansible Deployment

This directory deploys the Phase 1 foundation for the FK CĒSIS club platform.

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
              ansible_host: 192.0.2.10   # VM IP or hostname
              ansible_user: ubuntu       # SSH login user (e.g. ubuntu, admin)
#              ansible_ssh_private_key_file: ~/.ssh/id_ed25519   # uncomment if not using default key
```

**Quick SSH test** (replace `192.0.2.10` and `ubuntu` with your values):

```bash
ssh ubuntu@192.0.2.10 "echo OK"
```

A successful login confirms Ansible can reach the host.

### 2. Group vars — set domain and admin email

Edit `ansible/inventories/local_vm/group_vars/local_vm/vars.yml`. This controls all service subdomains.

```yaml
football_club_domain: "example.lv"            # your real domain
football_club_admin_email: "admin@example.lv"  # Caddy SMTP postmaster address
```

### 3. DNS names to point at the VM IP

For **subdomain mode** (production): create A records for these four subdomains, all resolving to `ansible_host`:

| Subdomain | Served by |
|---|---|
| `club.<domain>` | Dolibarr (WordPress-like admin portal) |
| `billing.<domain>` | Invoice Ninja |
| `n8n.<domain>` | n8n workflow engine |
| `agreements.<domain>` | Docuseal e-signature service |

Example for `example.lv`:

```
club.example.lv       → 192.0.2.10
billing.example.lv    → 192.0.2.10
n8n.example.lv        → 192.0.2.10
agreements.example.lv → 192.0.2.10
```

For **local mode** (`.lan` hostnames with internal TLS): add host entries on every client machine that will access the VM, then import Caddy's root CA certificate so browsers trust the self-signed HTTPS.

**a) `/etc/hosts` mapping** (run on each client):

```bash
sudo tee -a /etc/hosts <<EOF
192.168.x.x club.lan billing.lan n8n.lan agreements.lan
EOF
```

Replace `192.168.x.x` with the actual VM LAN IP.

**b) Import Caddy's internal CA certificate** (run on each client after the first Ansible run):

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

Edit `/tmp/local-vault.yml` with real or test values (see secret rules below).

**Step B — encrypt to the tracked location:**

```bash
ansible-vault encrypt --output ansible/inventories/local_vm/group_vars/local_vm/vault.yml \
  /tmp/local-vault.yml
```

This prompts for a vault password interactively, writes the encrypted file to the tracked location, and leaves `/tmp/local-vault.yml` as plaintext for your review. Delete it after confirming the output:

```bash
rm -f /tmp/local-vault.yml
```

**Step C — edit later:**

```bash
ansible-vault edit ansible/inventories/local_vm/group_vars/local_vm/vault.yml
```

The default editor (`$EDITOR`, usually `vim`) opens the decrypted contents. Save and exit to write.

### 5. Secret values for local VM testing

For local/development VMs you can safely use Stripe test keys provided by the vault example:

```yaml
vault_stripe_publishable_key: "pk_test_..."
vault_stripe_secret_key:     "sk_test_..."
vault_stripe_webhook_secret:  "whsec_test_..."
```

**Never commit live Stripe secrets** (`pk_live_`, `sk_live_`) to this repository.

For database passwords, encryption keys, and other secrets, generate random values:

```bash
# 32 bytes → base64 ≈ 44 chars (suitable for db passwords)
openssl rand -base64 32

# 64 bytes → base64 ≈ 88 chars (suitable for encryption keys)
openssl rand -base64 64
```

### Retry / dry-run

After every Ansible change, before applying:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook --check --diff \
  ansible/playbooks/site.yml --ask-vault-pass -K
```

(Identical to the "Run before applying" command in **Required checks** above.)

If the dry run succeeds, omit `--diff` for shorter output, then apply with the `Apply to local VM` command below.

### Volume ownership note

InvoiceNinja runs as container user `ninja` (`999:999`) and requires write access to its `ninja_storage` named volume at `/app/storage`. The stack role creates the storage volume, initializes Laravel cache/session/view/log directories, and fixes ownership before `docker compose up`. Do not mount `/app/public`; the image ships built public assets there.

No broad ownership fix is applied to database volumes. MariaDB, PostgreSQL, n8n, Dolibarr, and Docuseal use their image defaults unless runtime evidence shows otherwise.

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

## Secret rules

Never commit plaintext secrets, vault passwords, generated `.env` files, API tokens, Stripe secrets, WhatsApp tokens, database passwords, or real ID document photos.
