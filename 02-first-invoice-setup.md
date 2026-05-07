# First Invoice Setup Plan — Manual Configuration

Generate your first test invoice in Invoice Ninja (v5 self-hosted, test mode) with Mollie checkout links. No sync script, no member app — just raw UI steps.

---

## Prerequisites

1. **Invoice Ninja** running (Docker setup from Phase 1).
2. **Mollie account** (test mode) — sign up at [dashboard.mollie.com](https://dashboard.mollie.com). Note your API key starting with `test_...` (Developers → API Keys).
3. **Invoice Ninja API token** — Settings → Account Management → API Tokens → Create new token.

---

## Step 1 — Configure Invoice Ninja Global Settings

### 1A. Company Details
**Path:** `Settings → Company Settings`

| Field             | Value                           |
|-------------------|---------------------------------|
| Company Name      | FK ČESIS                        |
| Tagline           | Biedrība                        |
| Website           | (leave blank or `fk-cesis.lv`)  |
| Address Line 1    | (your street address)           |
| City              | (your city)                     |
| Postal Code       | (your postal code)              |
| Country           | Latvia                          |
| Phone             | (optional)                      |
| Email             | (your club email)               |

### 1B. Bank Details
**Path:** `Settings → Company Details → Bank Details`

| Field    | Value                          |
|----------|--------------------------------|
| Bank Name| Swedbank                       |
| IBAN     | LV79 HABA 0551 0546 7051 1     |
| SWIFT/BIC| HABALV22                       |

### 1C. Localization
**Path:** `Settings → Localization`

| Field          | Value            |
|----------------|------------------|
| Language       | English (UI)     |
| Date Format    | d-m-Y            |
| Currency       | Euro (EUR)       |
| Locale         | lv_LV or en_GB   |

### 1D. Taxes
**Path:** `Settings → Taxes`

- Ensure **VAT/PVN is NOT enabled** — the club is not VAT-registered in Latvia.

---

## Step 2 — Configure Mollie Payment Gateway

**Path:** `Settings → Payment Settings → New Gateway`

1. Select **Mollie** from the dropdown → Click **Setup**.
2. **Credentials tab**:
   - **API Key**: Paste your `test_...` key from Mollie.
   - **Profile ID**: Leave blank (not required — Mollie uses API keys only).
   - **Test Mode**: ✅ Enable.
3. **Settings tab**:
   - **Label**: `Mollie Test`.
   - **Capture Card**: Leave default.
   - **Available Payment Types**: Enable **Credit Card** and **Bank Transfer**.
   - *Note*: Per forum thread [14256](https://forum.invoiceninja.com/t/ideal-mollie-only-shows-crecitcard/14256), Mollie only shows payment methods eligible for the client's country and currency. For testing with Latvian clients, you may only see Credit Card. To test Bank Transfer or iDEAL, temporarily set the client's country to Netherlands (NL).
4. **Limits/Fees tab**: Leave default.

Save.

**References:**
- [Invoice Ninja Payment Gateways Docs](https://invoiceninja.github.io/docs/user-guide/gateways)
- [Mollie on Invoice Ninja forum (legacy thread — outdated, June 2021)](https://forum.invoiceninja.com/t/invoice-ninja-v5-online-provider-mollie/7416) — note: Mollie IS now supported in v5
- [Mollie gateway troubleshooting forum](https://forum.invoiceninja.com/t/ideal-mollie-only-shows-crecitcard/14256)

---

## Step 3 — Create a Test Client (Individual)

### Option A: Via UI
**Path:** `Clients → New Client`

| Field         | Value                     |
|---------------|---------------------------|
| Name          | Jānis Bērziņš             |
| Email         | test@example.com          |
| Country       | Latvia                    |
| Currency      | EUR                       |

**Important**: In v5, when you leave `company_name` blank and fill in contact fields, Invoice Ninja treats the client as **individual**. There is no explicit dropdown for this — it's inferred from whether `company_name` is set.

Under **Contacts**, add the child's email. This is required — per [API docs](https://api-docs.invoicing.co/): *"When creating (or updating) a client you must include the child contacts with all mutating requests."*

### Option B: Via API (curl)

```bash
curl -X POST 'https://YOUR_IN_DOMAIN/api/v1/clients' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Token: YOUR_API_TOKEN' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{
    "company_name": "Jānis Bērziņš",
    "contacts": [
      {
        "first_name": "Jānis",
        "last_name": "Bērziņš",
        "email": "test@example.com",
        "is_primary": true
      }
    ],
    "country_id": 119,
    "currency_id": 97
  }'
```

**Finding country_id / currency_id**:
- `GET https://YOUR_IN_DOMAIN/api/v1/countries` — Latvia = `119`
- `GET https://YOUR_IN_DOMAIN/api/v1/currencies` — EUR = `97`
- Or set them manually in the UI after creation.

**Entity Type**: In v5, Invoice Ninja infers entity type server-side. Leaving `company_name` as a person's name (not a business name) and not setting a tax/VAT number makes it treat it as individual. No `classification` or `entity_type_id` field is exposed in the API.

---

## Step 4 — Create a Product/Service

**Path:** `Products → New Product`

| Field     | Value                           |
|-----------|---------------------------------|
| Product Key | Monthly Installment           |
| Notes     | Youth football membership fee   |
| Cost      | 30.00                           |
| Price     | 30.00                           |
| Quantity  | 1                               |

---

## Step 5 — Create the Test Invoice

**Path:** `Invoices → Create Invoice`

1. Select your test client (Jānis Bērziņš).
2. Add the product: "Monthly Installment" — Qty 1, Price €30.00.
3. **Due Date**: ~14 days from now.
4. **Custom Subject**: "Membership fee - Month August 2026".
5. Under **Payment Options**, ensure **Mollie** is enabled.
6. **Save as Draft** first → review → then send or preview.

---

## Step 6 — Test the Payment Flow

1. **Preview the PDF** — verify:
   - Club name (FK ČESIS) and reg. number appear.
   - Bank details are shown.
   - Line item shows €30.00.
   - "Pay Now" button/link appears.

2. **Send the invoice** — it emails the invoice to `test@example.com`.

3. **Open the invoice email** → click "Pay Now" → redirected to Mollie test checkout.

4. **Test payment**: In test mode, Mollie provides test card numbers (e.g., `4111 1111 1111 1111`). Complete a test payment.

5. **Verify**: Invoice status updates to **Paid** in Invoice Ninja.

---

## Step 7 — (Optional) Latvian Invoice Customization

### Approach A: Custom Fields (easiest)
**Path:** `Settings → Custom Fields`

Add Latvian labels for company info, bank details, etc. Much easier than editing HTML templates.

### Approach B: Custom HTML Invoice Design
**Path:** `Settings → Invoice Design → Customize`

1. Create a new design based on a template.
2. Edit HTML to translate field labels:
   - "Invoice" → "Rēķins"
   - "Amount" → "Summa"
   - "Due Date" → "Maksājuma termiņš"
   - etc.
3. Required field IDs are documented at: https://invoiceninja.github.io/docs/advanced-topics/custom-fields
4. Full customization: https://invoiceninja.github.io/docs/advanced-topics/templates

**Reference**: [Invoice Design (v4 docs — concept carries to v5)](https://invoice-ninja.readthedocs.io/en/latest/invoice_design.html)

---

## Step 8 — (Optional) Invoice Numbering

**Path:** `Settings → Invoice Design → Numbering`

- Default: `INV-0001`, `INV-0002` (acceptable for MVP).
- For custom format like `FK 2026/001`, check if v5 supports custom prefixes in Settings → Numbering.

---

## Troubleshooting Checklist

| Issue | Fix |
|---|---|
| Mollie payment methods not showing | Set client country to NL temporarily for testing (forum thread [14256](https://forum.invoiceninja.com/t/ideal-mollie-only-shows-crecitcard/14256)) |
| "422 Unprocessable Entity" on gateway setup | Double-check API key format (`test_...`), remove Profile ID if present |
| Invoice PDF missing company name | Ensure `company_name` is set in the client record — don't leave it empty (prevents "duplicate name" bug) |
| Currency not showing EUR | Check Settings → Localization; may need `DEFAULT_CURRENCY=EUR` in `.env` |
| Email not sending | Check Settings → Email → SMTP configuration |
| Can't find Latvia in country list | Use API `GET /countries` to find the correct ID |

---

## API References

| Resource | URL |
|---|---|
| Full API Reference | https://api-docs.invoicing.co/ |
| Payment Gateways | https://invoiceninja.github.io/docs/user-guide/gateways |
| Invoice Design | https://invoiceninja.github.io/docs/advanced-topics/templates |
| Custom Fields | https://invoiceninja.github.io/docs/advanced-topics/custom-fields |
| Developer Guide | https://invoiceninja.github.io/docs/developer-guide |
| Invoice Design (v4 — concept applies) | https://invoice-ninja.readthedocs.io/en/latest/invoice_design.html |

## Forum References

| Topic | URL |
|---|---|
| Mollie gateway support | https://forum.invoiceninja.com/t/invoice-ninja-v5-online-provider-mollie/7416 |
| iDEAL/Mollie payment methods not showing | https://forum.invoiceninja.com/t/ideal-mollie-only-shows-crecitcard/14256 |
| English/EUR not available in settings | https://forum.invoiceninja.com/t/english-and-euro-not-available-in-settings/10665 |
| Gateway activation in self-hosted | https://forum.invoiceninja.com/t/activating-payment-gateway-in-self-hosted-install/9770 |
