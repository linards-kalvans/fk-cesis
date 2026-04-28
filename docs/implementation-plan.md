# Football Club Platform — Implementation Plan

## Context

Self-hosted hybrid stack for a youth football club based in Latvia (EU/SEPA zone).

### Stack

| Service | Role | Image |
|---|---|---|
| **Dolibarr** | Member DB, calendar, attendance, documents | `dolibarr/dolibarr:latest` |
| **InvoiceNinja** | Recurring billing, payment tracking, coach invoices | `invoiceninja/invoiceninja-octane:latest` |
| **n8n** | Integration glue — WhatsApp polls, attendance sync, coach billing calc | `n8nio/n8n:latest` |
| **Docuseal** | Agreement template generation, e-signature collection | `docuseal/docuseal:latest` |
| **DocTR** | ID document OCR for registration prefill (on-demand, CPU) | `ghcr.io/mindee/doctr:api-cpu-latest` |
| **Stripe** | Payment gateway — card + SEPA EU (Latvia) | External API |
| **Caddy** | Reverse proxy + TLS termination | Already running |

### Architectural principle

- Dolibarr is the **system of record** for members, teams, and events.
- InvoiceNinja is the **system of record** for all financial transactions.
- n8n is the **event bus** — no direct DB coupling between Dolibarr and InvoiceNinja.
- All services communicate via REST APIs and webhooks only.

---

## Phase 1 — Infrastructure & Data Foundation

**Duration:** Weeks 1–4 | **Effort:** ~18h

### Goal
All four core services deployed, accessible, and verified working. Existing member roster imported. Stripe connection confirmed working for Latvia.

### Ansible deployment foundation

Phase 1 deployment is managed with Ansible. Docker Compose remains the runtime orchestrator, but host configuration must be rendered and applied from source-controlled Ansible roles instead of manual edits.

The deployment foundation targets an Ubuntu LTS VM first, then a production Ubuntu LTS host later. Ansible owns these host artifacts:

- `/opt/football-club/docker-compose.yml`
- `/opt/football-club/.env`
- `/etc/caddy/Caddyfile`
- `/opt/football-club/backup.sh`
- backup cron schedule

Secrets must come from Ansible Vault. Real `.env` files, vault passwords, API keys, Stripe secrets, WhatsApp tokens, database passwords, and real ID photos must never be committed.

Mandatory checks for Ansible changes:

```bash
ansible-lint
yamllint .
ansible-playbook --syntax-check ansible/playbooks/site.yml
ansible-playbook --check --diff ansible/playbooks/site.yml
```

After dry-run, apply the playbook to the Ubuntu LTS VM and run HTTP smoke checks against the real subdomains pointed to that VM.

### Docker Compose template

Ansible renders `/opt/football-club/docker-compose.yml` from the repository template:

```yaml
services:

  # ── Dolibarr ──────────────────────────────────────────────────────
  dolibarr:
    image: dolibarr/dolibarr:latest
    restart: unless-stopped
    environment:
      DOLI_DB_HOST: dolibarr-db
      DOLI_DB_NAME: dolibarr
      DOLI_DB_USER: dolibarr
      DOLI_DB_PASSWORD: ${DOLI_DB_PASSWORD}
      DOLI_ADMIN_LOGIN: admin
      DOLI_ADMIN_PASSWORD: ${DOLI_ADMIN_PASSWORD}
      DOLI_URL_ROOT: https://club.${DOMAIN}
      DOLI_AUTH: dolibarr
    volumes:
      - dolibarr_data:/var/www/html/documents
    depends_on:
      - dolibarr-db

  dolibarr-db:
    image: mariadb:10.6
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: dolibarr
      MYSQL_USER: dolibarr
      MYSQL_PASSWORD: ${DOLI_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DOLI_DB_ROOT_PASSWORD}
    volumes:
      - dolibarr_db_data:/var/lib/mysql

  # ── InvoiceNinja ──────────────────────────────────────────────────
  invoiceninja:
    image: invoiceninja/invoiceninja-octane:latest
    restart: unless-stopped
    environment:
      APP_ENV: production
      APP_DEBUG: "false"
      APP_URL: https://billing.${DOMAIN}
      APP_KEY: ${NINJA_APP_KEY}
      REQUIRE_HTTPS: "true"
      IS_DOCKER: "true"
      IN_USER_EMAIL: ${ADMIN_EMAIL}
      IN_PASSWORD: ${NINJA_ADMIN_PASSWORD}
      IN_USER: Admin
      DB_HOST: ninja-db
      DB_DATABASE: ninja
      DB_USERNAME: ninja
      DB_PASSWORD: ${NINJA_DB_PASSWORD}
      NINJA_LICENSE: self-hosted-open-source
    volumes:
      - ninja_storage:/app/storage
    depends_on:
      - ninja-db

  ninja-db:
    image: mariadb:10.6
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: ninja
      MYSQL_USER: ninja
      MYSQL_PASSWORD: ${NINJA_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${NINJA_DB_ROOT_PASSWORD}
    volumes:
      - ninja_db_data:/var/lib/mysql

  # ── n8n ───────────────────────────────────────────────────────────
  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    environment:
      N8N_HOST: n8n.${DOMAIN}
      N8N_PORT: 5678
      WEBHOOK_URL: https://n8n.${DOMAIN}/
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: n8n-db
      DB_POSTGRESDB_DATABASE: n8n
      DB_POSTGRESDB_USER: n8n
      DB_POSTGRESDB_PASSWORD: ${N8N_DB_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - n8n-db

  n8n-db:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${N8N_DB_PASSWORD}
    volumes:
      - n8n_db_data:/var/lib/postgresql/data

  # ── Docuseal ──────────────────────────────────────────────────────
  docuseal:
    image: docuseal/docuseal:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      SECRET_KEY_BASE: ${DOCUSEAL_SECRET_KEY}
      WORKDIR: /data
    volumes:
      - docuseal_data:/data

  # ── DocTR OCR — on-demand, not always-on ─────────────────────────
  doctr-api:
    image: ghcr.io/mindee/doctr:api-cpu-latest
    restart: "no"
    deploy:
      resources:
        limits:
          memory: 512m

volumes:
  dolibarr_data:
  dolibarr_db_data:
  ninja_storage:
  ninja_db_data:
  n8n_data:
  n8n_db_data:
  docuseal_data:
```

Ansible renders `/opt/football-club/.env` from encrypted Ansible Vault variables. Never commit generated `.env` files or plaintext secrets.

### Caddy configuration

Ansible installs and manages Caddy. If the target host already has a Caddyfile, back it up before replacing it with the managed configuration.

Caddy routing mode is controlled by the `football_club_caddy_mode` inventory variable:

- `subdomain` — each service gets its own subdomain with ACME TLS (production default)
- `local` — `.lan` hostnames with Caddy internal TLS (local VM)

**Subdomain mode Caddyfile:**

```
club.{$DOMAIN} {
  reverse_proxy dolibarr:80
}

billing.{$DOMAIN} {
  reverse_proxy invoiceninja:80
}

n8n.{$DOMAIN} {
  reverse_proxy n8n:5678
}

agreements.{$DOMAIN} {
  reverse_proxy docuseal:3000
}
```

**Local mode Caddyfile:**

```
{
  http_port 80
  https_port 443
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

Service containers receive correctly computed `*_URL` environment variables so self-referential links (emails, redirects, webhooks) match the external access pattern.

**Local client setup:**
After deploying the local VM, each Linux client needs the VM IP added to `/etc/hosts`:

```bash
sudo tee -a /etc/hosts <<EOF
192.168.x.x club.lan billing.lan n8n.lan agreements.lan
EOF
```

And Caddy's internal CA certificate imported:

```bash
scp user@vm:/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/caddy-local-ca.crt
sudo cp ~/caddy-local-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

**Local client setup:**
After deploying the local VM, each Linux client needs the VM IP added to `/etc/hosts`:

```bash
sudo tee -a /etc/hosts <<EOF
192.168.x.x club.lan billing.lan n8n.lan agreements.lan
EOF
```

And Caddy's internal CA certificate imported:

```bash
scp user@vm:/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt ~/caddy-local-ca.crt
sudo cp ~/caddy-local-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

### Dolibarr initial configuration

After first boot, enable the following modules via **Home → Setup → Modules**:

- `Members` — member lifecycle management
- `Agenda` — event/calendar with recurrence support
- `Resources` — bookable resources (training ground)
- `Documents` — file attachment per member record
- `API REST` — required for n8n integration

Enable REST API and generate an API key: **Setup → Security → REST API keys**.

### Member import

Prepare a CSV with columns: `firstname`, `lastname`, `email`, `phone`, `birth_date`, `morphy` (physical person = `p`), `public` (0), `statut` (1 = active).

Import via: **Members → Import → CSV**. Alternatively use the REST API endpoint `POST /api/index.php/members` to import programmatically.

Mirror the same list into InvoiceNinja as clients: **Clients → Import → CSV** with columns: `name`, `email`, `phone`.

### Backup script

Ansible installs `/opt/football-club/backup.sh`:

```bash
#!/bin/bash
set -e
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/football-club/$DATE"
mkdir -p "$BACKUP_DIR"

# Dump all databases
docker exec dolibarr-db mysqldump -u root -p${DOLI_DB_ROOT_PASSWORD} dolibarr > "$BACKUP_DIR/dolibarr.sql"
docker exec ninja-db mysqldump -u root -p${NINJA_DB_ROOT_PASSWORD} ninja > "$BACKUP_DIR/ninja.sql"
docker exec n8n-db pg_dump -U n8n n8n > "$BACKUP_DIR/n8n.sql"

# Backup Dolibarr documents volume
docker run --rm -v dolibarr_data:/data -v "$BACKUP_DIR":/backup alpine \
  tar czf /backup/dolibarr_documents.tar.gz /data

# Backup n8n workflows
docker run --rm -v n8n_data:/data -v "$BACKUP_DIR":/backup alpine \
  tar czf /backup/n8n_workflows.tar.gz /data

# Sync to offsite (configure target)
rsync -az "$BACKUP_DIR" user@offsite-host:/backups/football-club/

# Retain last 30 days locally
find /opt/backups/football-club -maxdepth 1 -mtime +30 -type d -exec rm -rf {} +

echo "Backup complete: $BACKUP_DIR"
```

Ansible schedules the backup cron entry: `0 2 * * * /opt/football-club/backup.sh >> /var/log/football-backup.log 2>&1`

### Phase 1 acceptance tests

```
[ ] ansible-lint passes
[ ] yamllint . passes
[ ] ansible-playbook --syntax-check ansible/playbooks/site.yml passes
[ ] ansible-playbook --check --diff ansible/playbooks/site.yml passes
[ ] Full Ansible apply to Ubuntu LTS VM succeeds
[ ] docker compose -f /opt/football-club/docker-compose.yml config succeeds on the VM
[ ] Caddy validates and reloads successfully
[ ] Expected containers are running or healthy where health checks exist
[ ] GET https://club.{DOMAIN}/api/index.php/members — returns 200 with member list
[ ] GET https://billing.{DOMAIN} — InvoiceNinja admin UI loads
[ ] GET https://n8n.{DOMAIN} — n8n UI loads
[ ] GET https://agreements.{DOMAIN} — Docuseal UI loads
[ ] Stripe test mode: create a €1 invoice in InvoiceNinja, pay via test card 4242 4242 4242 4242
    — invoice status changes to Paid within 60 seconds
[ ] Stripe test SEPA: confirm SEPA payment method appears in client portal
[ ] Backup restore test: restore dolibarr.sql to a temp container, verify member count matches
[ ] Dolibarr API key auth: curl -H "DOLAPIKEY: {key}" https://club.{DOMAIN}/api/index.php/members
    — returns member array, not 401
```

> **GATE:** Do not proceed to Phase 2 until Stripe Latvia SEPA and card payments are confirmed working with a real bank account, not just test mode.

---

## Phase 2 — Billing Engine

**Duration:** Weeks 5–8 | **Effort:** ~20h

### Goal

InvoiceNinja fully configured for recurring monthly billing. 5 pilot members invoiced through one complete payment cycle. Overdue reminder sequence working.

### InvoiceNinja configuration

**Products**
Create a product: `Membership — Monthly` at the club's monthly membership rate (e.g. €30.00), tax rate per Latvian VAT rules.

**Invoice template**
Customise the default invoice PDF template to include:
- Club name, logo, registration number
- Club bank account (IBAN) for manual bank transfer fallback
- Stripe payment link button (auto-included)
- Footer: contact email, club address

**Email templates**
Configure under **Settings → Templates & Reminders**:

- `Invoice` — friendly tone, includes payment link, mentions both card and bank transfer options
- `Reminder 1` (day +7) — gentle nudge, reattach invoice PDF
- `Reminder 2` (day +14) — firmer tone, mention outstanding balance
- `Reminder 3` (day +30) — final notice, include treasurer contact
- `Payment` — thank-you confirmation with receipt summary
- `Partial Payment` — acknowledges partial payment, shows remaining balance

**Reminder schedule**
Settings → Templates & Reminders → Enable reminders:
- Reminder 1: 7 days after due date
- Reminder 2: 14 days after due date
- Reminder 3: 30 days after due date

### Pro-rata subscription logic

For new members joining mid-year, calculate the subscription start and number of billing cycles:

```
months_remaining = 13 - join_month   # e.g. join in August (month 8) → 5 months
subscription_end = December 31 of current year
```

When creating a recurring subscription in InvoiceNinja:
- **Frequency:** Monthly
- **Start date:** 1st of next month after joining (or immediate if joining on the 1st)
- **Auto-billing:** Enabled (card on file via Stripe)
- **Number of cycles:** `months_remaining` (subscription auto-pauses in January; renew annually)

In January each year, update all subscriptions to a full 12-cycle annual run.

### n8n workflow: New member → InvoiceNinja subscription

Trigger: Dolibarr webhook on member status change to `active`.

```
1. Receive webhook payload (member_id, join_date, email, name)
2. Calculate months_remaining from join_date
3. Check if client already exists in InvoiceNinja (GET /api/v1/clients?email={email})
4. If not exists: POST /api/v1/clients with name, email, phone
5. GET client_id from response
6. POST /api/v1/subscriptions:
   {
     "client_id": "{client_id}",
     "product_ids": ["{membership_product_id}"],
     "frequency_id": 5,          // monthly
     "remaining_cycles": months_remaining,
     "auto_bill": "always",
     "next_send_date": "{first_of_next_month}"
   }
7. Log result to n8n execution log
```

### Coach invoicing setup

Create coaches as **Vendors** in InvoiceNinja (not clients):
- Vendor name, IBAN, email
- Create expense category: `Coach Session Fee — Training` and `Coach Session Fee — Competition`
- Session rates stored as InvoiceNinja products (e.g. `Training Session — Coach` at agreed rate per session)

Coach invoices are generated at month-end from attendance data (see Phase 3).

### Phase 2 acceptance tests

```
[ ] Pilot member receives invoice email — renders correctly on mobile (iOS + Android)
[ ] Payment link in email opens Stripe checkout — card payment completes, invoice → Paid
[ ] Partial payment: pay 50% of invoice — remaining balance shown correctly in client portal
[ ] Overpayment: pay 150% — credit applied to next invoice automatically
[ ] Reminder 1 manually triggered for overdue test invoice — correct email received
[ ] Reminder email contains correct outstanding amount and live payment link
[ ] Pro-rata test: create subscription with start date Aug 1 — 5 invoices generated, not 12
[ ] Treasurer dashboard: all 5 pilot members visible, correct payment status per member
[ ] Run pilot for one full 4-week cycle without manual intervention
[ ] Collect written feedback from all 5 pilot members
```

> **GATE (MVP):** Billing working for 5 members across one full cycle = working payment system. Phases 3–5 are automation layers. Club can operate manually without them.

---

## Phase 3 — Attendance Automation (n8n + WhatsApp)

**Duration:** Weeks 9–14 | **Effort:** ~35h

### Goal

Automated attendance polls sent to WhatsApp groups before each training/event. Responses parsed and stored in Dolibarr. Month-end coach billing calculated from attendance data.

### Prerequisites — Meta Business setup (start in parallel with Phase 2)

1. Register the club as a business on [Meta Business Suite](https://business.facebook.com)
   - Legal entity: Latvian biedrība (association) qualifies
   - Required docs: registration certificate, address, website or social media page
2. Apply for WhatsApp Business API access via a BSP (Business Solution Provider)
   - Recommended: use Meta's own Cloud API (free, no BSP markup)
   - Dedicated phone number required (SIM or virtual number)
3. Submit message templates for approval (1–5 business days per template):

**Template 1: Training poll**
```
Training today: {{1}} at {{2}} — {{3}}
Are you coming?
[Button: ✅ Coming] [Button: ❌ Not coming] [Button: ❓ Maybe]
```

**Template 2: Competition initial poll**
```
📅 Upcoming competition: {{1}} on {{2}} at {{3}}
Initial attendance check — are you planning to come?
[Button: ✅ Yes] [Button: ❌ No] [Button: ❓ Unsure]
```

**Template 3: Competition final confirmation**
```
⚽ Final confirmation: {{1}} is in 2 days ({{2}}).
Please confirm your attendance.
[Button: ✅ Confirmed] [Button: ❌ Can't make it]
```

> All outbound template messages must be pre-approved by Meta before use. Use interactive button messages (not free-text polls) — button responses are machine-parseable and do not require NLP.

### Dolibarr event schema

Each event in Dolibarr Agenda should have:
- `label`: event name
- `datep`: start datetime (Unix timestamp)
- `location`: venue name
- `type`: custom field — one of `training`, `competition`, `special`
- `poll_lead_days`: custom field — days before event to send initial poll (training = 0 = morning-of, competition = configurable e.g. 14)
- `squad_id`: Dolibarr group ID of the squad this event belongs to
- `coach_id`: Dolibarr member ID of the assigned coach

Add custom fields via: **Dolibarr → Setup → Extra fields → Agenda**.

### n8n workflow: Daily poll dispatcher

**Trigger:** Cron — every day at 07:00 local time

```
1. GET /api/index.php/agendaevents?sortfield=datep&sortorder=ASC&limit=50
   Filter: datep >= today, datep <= today + 21 days, status = 1 (confirmed)

2. For each event:
   a. Calculate poll_send_datetime:
      - type == "training"    → today at 07:00 (morning-of)
      - type == "competition" → event_date - poll_lead_days at 09:00
      - type == "special"     → event_date - poll_lead_days at 09:00

   b. Check if poll already sent (query n8n KV store for key "poll_sent_{event_id}")
      If already sent: skip

   c. If poll_send_datetime <= now:
      - GET squad members: GET /api/index.php/members?groupid={squad_id}
      - For each member with phone number:
        POST to WhatsApp Cloud API /messages with template + event variables
      - Store "poll_sent_{event_id}" = true in n8n KV store
      - Log: event_id, members_polled, timestamp
```

### n8n workflow: WhatsApp response handler

**Trigger:** Webhook — WhatsApp Cloud API webhook (POST to `https://n8n.{DOMAIN}/webhook/whatsapp`)

```
1. Verify webhook signature (X-Hub-Signature-256 header)

2. Extract from payload:
   - from: sender phone number (E.164 format)
   - button_reply.id: one of "coming", "not_coming", "maybe"
   - context.id: original message ID (to match to event)

3. Look up member in Dolibarr:
   GET /api/index.php/members?phone={from}
   If no match: log warning "Unknown number {from}", send WA message "Reply not recognised — contact coach directly", exit

4. Look up event from context.id:
   Query n8n KV store for "poll_message_id_{message_id}" → returns event_id
   If no match: log warning, exit

5. Map button_reply.id to attendance status:
   "coming"     → status = 1
   "not_coming" → status = 2
   "maybe"      → status = 3

6. Upsert attendance record in Dolibarr:
   POST /api/index.php/agendaevents/{event_id}/attendees
   Body: { "fk_user": member_id, "status": status }
   (If record exists, PATCH instead)

7. Log: member_id, event_id, status, timestamp
```

### n8n workflow: Month-end coach billing

**Trigger:** Cron — 1st of each month at 08:00

```
1. Calculate period: first day to last day of previous month

2. GET all events in period from Dolibarr:
   GET /api/index.php/agendaevents?date_start={period_start}&date_end={period_end}&status=1

3. For each unique coach_id in events:
   a. Filter events assigned to this coach
   b. Count by type:
      training_sessions = count(type == "training")
      competition_sessions = count(type == "competition")

   c. Calculate total:
      total = (training_sessions × RATE_TRAINING) + (competition_sessions × RATE_COMPETITION)
      (Rates stored as n8n environment variables)

   d. Create draft expense in InvoiceNinja:
      POST /api/v1/expenses
      {
        "vendor_id": "{coach_vendor_id}",
        "amount": total,
        "category_id": "{coach_session_category_id}",
        "date": "{last_day_of_month}",
        "public_notes": "Training: {training_sessions} sessions, Competition: {competition_sessions} sessions",
        "should_be_invoiced": false
      }

   e. Send notification email to treasurer with draft expense summary

4. Log: month, coaches_processed, total_expense_created
```

### n8n error alerting

Add a global error handler in n8n (Settings → Error Workflow):

```
On any workflow failure:
1. Send email to club admin: workflow name, error message, timestamp, execution ID
2. Log to n8n execution log with status ERROR
```

### Phase 3 acceptance tests

```
[ ] Create a training event in Dolibarr today → poll message arrives in test WA group within 5 minutes of 07:00
[ ] Poll message contains correct event name, time, and venue
[ ] Tap "Coming" from test number → attendance record created in Dolibarr within 30 seconds
[ ] Tap "Not coming" from same number → record updated, not duplicated
[ ] Unknown number replies → workflow logs warning, no crash, no record created
[ ] Competition event: poll sent N days before (set poll_lead_days = 2 for test) — arrives on time
[ ] Competition second confirmation: second poll sent 2 days before event
[ ] Month-end billing: seed 10 attendance records across 2 coaches → billing workflow creates
    correct draft expenses in InvoiceNinja matching expected session counts and amounts
[ ] Simulate n8n container restart → on restart, no duplicate polls sent for already-polled events
[ ] Trigger a workflow error deliberately → error email received by admin within 2 minutes
[ ] Run live with one squad for 2 full weeks before expanding to all squads
[ ] Response rate ≥ 70% across 2-week pilot
```

> **Risk:** Meta verification timing is unpredictable (1–14 days). Start this immediately in parallel with Phase 2. If delayed, use email or Telegram polls as a temporary fallback — the Dolibarr attendance write-back still works, just via a different channel.

---

## Phase 4 — Agreement Management

**Duration:** Weeks 15–18 | **Effort:** ~25h

### Goal

New member registration flow: HTML form → ID OCR prefill → member created in Dolibarr → agreement generated and e-signed via Docuseal → signed PDF stored → InvoiceNinja subscription triggered automatically.

### Registration form

Build a single-page HTML form hosted at `https://club.{DOMAIN}/join` (can be a static file served by Caddy or a simple PHP page on the Dolibarr server).

Required fields:
- Parent: first name, last name, email, phone (E.164)
- Child: first name, last name, date of birth, squad preference
- ID document photo upload (JPEG/PNG, max 5MB)
- Consent checkbox: "I agree to the club's data processing terms"

On submit: POST form data + file to `https://n8n.{DOMAIN}/webhook/registration`

### n8n workflow: New member registration

**Trigger:** Webhook — POST from registration form

```
1. Validate required fields — return 400 with field errors if missing

2. Save ID photo to temp storage (/tmp/id_{uuid}.jpg)

3. Call DocTR OCR API:
   POST http://doctr-api:8080/v1/ocr
   Body: { image: base64(id_photo) }

   Extract:
   - ocr_firstname: first name from document
   - ocr_lastname: last name from document
   - ocr_dob: date of birth from document
   - ocr_doc_number: document number

4. Validate OCR vs form data:
   name_match = fuzzy_match(form.child_lastname, ocr_lastname, threshold=80%)
   dob_match = form.child_dob == ocr_dob

   If name_match == false OR dob_match == false:
     Set flag: requires_manual_review = true
     Send alert email to admin: "Registration requires manual review — {child_name}"
     Continue flow (do not block — admin reviews asynchronously)

5. Create member in Dolibarr:
   POST /api/index.php/members
   {
     "firstname": form.child_firstname,
     "lastname": form.child_lastname,
     "email": form.parent_email,
     "phone": form.parent_phone,
     "birth_date": form.child_dob,
     "note_private": "ID doc: {ocr_doc_number}",
     "statut": 0    // pending — not active until agreement signed
   }
   Store returned member_id

6. Generate agreement via Docuseal:
   POST https://agreements.{DOMAIN}/api/v1/submissions
   {
     "template_id": "{MEMBERSHIP_TEMPLATE_ID}",
     "send_email": true,
     "submitters": [
       {
         "role": "Parent",
         "email": form.parent_email,
         "name": form.parent_firstname + " " + form.parent_lastname,
         "fields": [
           { "name": "child_name", "default_value": form.child_firstname + " " + form.child_lastname },
           { "name": "child_dob",  "default_value": form.child_dob },
           { "name": "squad",      "default_value": form.squad_preference },
           { "name": "year",       "default_value": current_year },
           { "name": "join_date",  "default_value": today }
         ]
       }
     ]
   }
   Store returned submission_id
   Store in n8n KV: "registration_{submission_id}" = { member_id, form_data }

7. Delete temp ID photo from /tmp

8. Return 200 to form with message: "Thank you — check your email to sign your membership agreement."
```

### n8n workflow: Agreement signed → activate member

**Trigger:** Webhook — Docuseal completion webhook (configure in Docuseal → Settings → Webhooks)

```
1. Receive payload: { submission_id, status: "completed", document_url }

2. Look up registration from KV: "registration_{submission_id}" → member_id, form_data

3. Download signed PDF from document_url

4. Attach PDF to Dolibarr member:
   POST /api/index.php/documents
   {
     "modulepart": "member",
     "id": member_id,
     "filename": "agreement_{member_id}_{year}.pdf",
     "filecontent": base64(signed_pdf)
   }

5. Activate member in Dolibarr:
   PUT /api/index.php/members/{member_id}
   { "statut": 1 }   // active

6. Trigger InvoiceNinja subscription creation (same as Phase 2 n8n workflow)
   Pass: member_id, email, join_date

7. Send welcome email to parent with:
   - Confirmation of membership
   - First invoice ETA (1st of next month)
   - WhatsApp group join link for their squad

8. Log: member_id, submission_id, activated_at
```

### Docuseal template setup

In Docuseal UI (`https://agreements.{DOMAIN}`):
1. Upload club membership agreement as PDF
2. Add fields with variable names matching the `fields` array above:
   - `child_name` — text field
   - `child_dob` — text field
   - `squad` — text field
   - `year` — text field
   - `join_date` — text field
   - `parent_signature` — signature field (assigned to "Parent" role)
   - `parent_date` — date field (auto-filled on signing)
3. Note the `template_id` from the URL and store in n8n env vars

### DocTR service management

DocTR is resource-intensive and registrations are infrequent. Manage it with:

```bash
# Start before n8n calls it (n8n can issue this via SSH Execute node)
docker compose -f /opt/football-club/docker-compose.yml up -d doctr-api

# n8n calls the OCR endpoint, then:
docker compose -f /opt/football-club/docker-compose.yml stop doctr-api
```

Alternatively: keep DocTR always-on if skuby7 has ≥4 GB RAM available.

### Phase 4 acceptance tests

```
[ ] Submit registration form with a real Latvian ID card photo
    → OCR extracts lastname and DOB correctly
[ ] Submit with intentionally mismatched name
    → requires_manual_review flag set, admin email received
[ ] Submit valid registration
    → member created in Dolibarr with statut=0 (pending)
[ ] Parent receives Docuseal signing email within 2 minutes of form submission
[ ] Pre-filled fields in agreement PDF are correct (name, DOB, squad, year)
[ ] Sign agreement on iOS Safari — signing UX completes without errors
[ ] Sign agreement on Android Chrome — signing UX completes without errors
[ ] Post-signature: signed PDF attached to member record in Dolibarr within 3 minutes
[ ] Post-signature: member statut updated to 1 (active) in Dolibarr
[ ] Post-signature: InvoiceNinja recurring subscription created automatically
[ ] Post-signature: welcome email received by parent with WhatsApp group link
[ ] DocTR accuracy benchmark: process 10 real Latvian ID document photos
    — target ≥80% correct extraction on lastname + dob fields
[ ] End-to-end test: 3 real test registrations through full flow without manual intervention
```

> **OCR note:** If DocTR accuracy is below 80% on Latvian IDs, swap to Eden AI (API key, ~€0.01/document) by changing the n8n OCR call from the DocTR endpoint to `POST https://app.edenai.run/v2/ocr/identity_parser`. No other changes needed.

---

## Phase 5 — Full Rollout & Handover

**Duration:** Weeks 19–20 | **Effort:** ~22h

### Goal

All members migrated. WhatsApp polling live for all squads. Monitoring configured. Treasurer can operate system independently. Runbooks written and tested.

### Full migration tasks

```
1. Export all remaining members from existing system (spreadsheet etc.)
2. Bulk-import into Dolibarr (CSV or REST API batch)
3. Bulk-create InvoiceNinja clients and subscriptions (can script this in Python/bash using IN REST API)
4. Add all coaches as Vendors in InvoiceNinja
5. Build out full Dolibarr event calendar — recurring training series for each squad
6. Assign squad_id and coach_id to all events
7. Add all squad member phone numbers to Dolibarr member records (required for WA polling)
8. Activate WhatsApp polling for all squads
9. Send communication to all parents: new billing system, first invoice date, how to pay
```

### Monitoring

Grafana Alloy (already running on skuby7 → linardshomelab Grafana Cloud):

Add to existing `alloy.config`:

```hcl
prometheus.scrape "football_services" {
  targets = [
    {"__address__" = "dolibarr:80",      "service" = "dolibarr"},
    {"__address__" = "invoiceninja:80",  "service" = "invoiceninja"},
    {"__address__" = "n8n:5678",         "service" = "n8n"},
    {"__address__" = "docuseal:3000",    "service" = "docuseal"},
  ]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
}
```

Additionally configure UptimeRobot (free tier) with HTTP monitors for all four service domains — alert to club admin email if any service returns non-200 for >2 consecutive checks.

### Treasurer runbook (produce as separate `TREASURER.md`)

Document these three core tasks in plain language:

1. **Add a new member manually** (for cases where automated flow fails)
   - Create in Dolibarr → Members → New
   - Create corresponding client in InvoiceNinja → Clients → New
   - Create subscription in InvoiceNinja → Subscriptions → New

2. **Check payment status for a member**
   - InvoiceNinja → Clients → [member name] → Invoices tab
   - Shows: all invoices, status (paid/overdue/partial), outstanding balance

3. **Send a manual payment reminder**
   - InvoiceNinja → Invoices → filter by Overdue
   - Select invoice → Actions → Send Reminder

### Ops runbook (produce as separate `OPS.md`)

Document:

1. **Restart a failed service:** `docker compose restart {service_name}`
2. **View service logs:** `docker compose logs -f {service_name} --tail=100`
3. **Upgrade Dolibarr:** pull new image → `docker compose pull dolibarr` → `docker compose up -d dolibarr` → verify admin panel loads → run any pending migrations via admin UI
4. **Upgrade InvoiceNinja:** pull → up -d → `docker exec invoiceninja php artisan migrate --force`
5. **Upgrade n8n:** pull → up -d → verify all workflows show as active
6. **Restore from backup:** documented step-by-step with exact commands
7. **Export n8n workflows:** Settings → Export all → save as `n8n_workflows_{date}.json` to backup location

### Phase 5 acceptance tests (go-live gates)

```
[ ] 100% of active members have a Dolibarr record
[ ] 100% of active members have an active InvoiceNinja subscription
[ ] One full monthly billing cycle completed for all members without manual intervention
[ ] Zero failed reminder emails in InvoiceNinja email log
[ ] WhatsApp polls running for all squads for ≥2 weeks with ≥70% response rate
[ ] At least one new member registered through full automated flow
    (form → OCR → agreement → billing activation)
[ ] Treasurer independently completes all 3 runbook tasks without assistance
[ ] Ops runbook tested: a second person restarts a container and runs an upgrade from the doc alone
[ ] 30-day uptime data shows ≥99% uptime across all four services
[ ] Grafana dashboards show metrics for all services
[ ] UptimeRobot alerts confirmed working (take a service down briefly to trigger alert)
[ ] All n8n workflows exported and stored in backup location
[ ] Emergency contact list documented: who to contact if system is down and you're unavailable
```

---

## Risk Register

| Risk | Severity | Phase | Mitigation |
|---|---|---|---|
| Meta business verification rejected or delayed | HIGH | Ph 3 | Start in Phase 2 parallel. Fallback: email/Telegram polls until WA live. Never block billing on this. |
| Stripe Latvia SEPA payments don't work | HIGH | Ph 1 | Test with real Latvian bank account in Phase 1 before any other phase. Card-only fallback if SEPA fails. |
| WA response parsing breaks on unexpected input | MED | Ph 3 | Use interactive button messages (not free-text). Unrecognised input → log + alert, no crash. |
| DocTR OCR poor accuracy on Latvian IDs | MED | Ph 4 | OCR is prefill only, not a gate. Low accuracy = more manual review. Fallback: Eden AI API (~€0.01/doc). |
| n8n workflow failure causes missed polls | MED | Ph 3–5 | Error alerting on all flows. Manual attendance entry in Dolibarr always available as fallback. |
| Treasurer can't operate system after handover | MED | Ph 5 | Day-to-day tasks in IN and Dolibarr need no technical knowledge. Write 1-page cheat sheet for 3 core tasks. |
| skuby7 RAM insufficient for full stack (~2 GB peak) | LOW | Ph 1 | Check current RAM. If <4 GB, upgrade to Hetzner CX32 (~€8.50/mo). DocTR is on-demand only. |
| LFF/COMET requires specific digital format | LOW | Ph 4 | Dolibarr CSV export maps to LFF fields manually. Document the field mapping once. |

---

## Environment variables reference

All variables go in `/opt/football-club/.env`:

```bash
# Shared
DOMAIN=yourdomain.lv

# Dolibarr
DOLI_DB_PASSWORD=
DOLI_DB_ROOT_PASSWORD=
DOLI_ADMIN_PASSWORD=
DOLI_API_KEY=                    # generated in Dolibarr admin after setup

# InvoiceNinja
NINJA_APP_KEY=                   # generate with: php artisan key:generate --show
NINJA_ADMIN_PASSWORD=
NINJA_DB_PASSWORD=
NINJA_DB_ROOT_PASSWORD=
NINJA_API_KEY=                   # generated in IN admin → API Tokens

# n8n
N8N_ENCRYPTION_KEY=              # random 32-char string
N8N_DB_PASSWORD=

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Docuseal
DOCUSEAL_SECRET_KEY=             # random 64-char string
DOCUSEAL_API_KEY=                # generated in Docuseal admin
MEMBERSHIP_TEMPLATE_ID=          # from Docuseal after template created

# WhatsApp Business API
WA_PHONE_NUMBER_ID=
WA_ACCESS_TOKEN=
WA_WEBHOOK_VERIFY_TOKEN=         # random string, configured in Meta dashboard
WA_TEMPLATE_TRAINING=            # approved template name
WA_TEMPLATE_COMPETITION_INITIAL= # approved template name
WA_TEMPLATE_COMPETITION_FINAL=   # approved template name

# Coach billing rates (EUR)
RATE_TRAINING_SESSION=           # e.g. 25
RATE_COMPETITION_SESSION=        # e.g. 40

# Alerts
ADMIN_EMAIL=

# DocTR (optional — if keeping always-on)
DOCTR_API_URL=http://doctr-api:8080
```

---

## Effort summary

| Phase | Description | Duration | Effort |
|---|---|---|---|
| 1 | Infrastructure & data foundation | Weeks 1–4 | ~18h |
| 2 | Billing engine | Weeks 5–8 | ~20h |
| 3 | WhatsApp + n8n automation | Weeks 9–14 | ~35h |
| 4 | Agreement management + OCR | Weeks 15–18 | ~25h |
| 5 | Full rollout + handover | Weeks 19–20 | ~22h |
| **Total** | | **~20 weeks** | **~120h** |

Assumes part-time solo work (~6–8h/week). Phases 1–2 can be compressed into 2 focused weeks if needed.

**Phase 3 is the longest** due to Meta verification lead time and WhatsApp template approval — both have external dependencies outside your control. Build buffer here.

**Phase 2 is the MVP gate** — billing working for 5 members = functional payment system. Everything after is automation.
