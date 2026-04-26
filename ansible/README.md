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

1. Create an Ubuntu LTS VM.
2. Ensure SSH works for the inventory user.
3. Point these real DNS names to the VM IP:
   - `club.<domain>`
   - `billing.<domain>`
   - `n8n.<domain>`
   - `agreements.<domain>`
4. Update `ansible/inventories/local_vm/hosts.yml` with the VM IP.
5. Update `ansible/group_vars/local_vm/vars.yml` with the real domain and admin email.
6. Create encrypted `ansible/group_vars/local_vm/vault.yml` from `vault.example.yml`.

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
