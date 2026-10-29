# Production proxy/debug/logging rollout — completed, 2026-10-29

## Outcome and remaining failures

**The explicitly approved, backup-gated production proxy fix was applied and
independently verified.** Debug remains false, Laravel no longer trusts all
proxies, nginx normalizes the verified host ingress and removes supported
forwarded headers before PHP, and warning/error logging works.

**The overall deployment is not all green:** the existing MMS Invoice Ninja
credential still receives **403 `Invalid token`**, exactly as before this
maintenance. The observed legacy backup job was not repaired; the user confirmed
that routine daily backups are handled by `server-backups` and deferred that
work here. This report does not assess that project's backup coverage. No
credential was created, changed or rotated, and no scheduled backup configuration
was changed under this approval.

The prior [read-only preflight](production-security-preflight-2026-10-29.md) is
a historical pre-change snapshot. This report takes precedence for the current
proxy/debug/logging state. The [proxy runbook](invoiceninja-proxy-hardening.md)
explains the threat boundary; broader shared-network/FastCGI isolation remains
separate work.

## Approval and strict scope

The user explicitly clicked **“Approve backup-gated production fix”** after the
proposal described fresh private backup/recovery, a temporary interruption and
recreation of only Invoice Ninja/nginx. The authorized target was
`deploy@netcup-prod-1.tail45ce0a.ts.net`, actual hostname `netcup-prod-1`, project
`/opt/football-club`, Compose project `football-club`.

Only the following live configuration changed:

- Keep `APP_DEBUG` false as an explicit environment string.
- Add `LOG_CHANNEL=stack` and `LOG_LEVEL=warning`.
- Replace `TRUSTED_PROXIES='*'` with `127.0.0.1,::1`.
- Select and install the VM-verified nginx startup script and Laravel config.

There were no image upgrades/pulls/rebuilds, secret rotations, Caddy changes,
database-schema/migration changes, network/port/volume-definition changes,
full-stack Ansible runs, MMS startup/migrations or forced business jobs. `.env`
remained byte-for-byte unchanged. No Vault file was read or decrypted.

## Pre-apply verification

- Exact host, image and cached-tag drift guards passed for all eight services.
  Production retained its own MariaDB **12.3.2**, not the VM's 11.8.6.
- The new nginx files' SHA256 values matched the files actually deployed and
  verified on the VM. Original production nginx files/command matched the
  pre-fix Git baseline recorded in the preflight.
- The isolated proxy harness also passed **on production's Docker engine using
  the actual accepted production PHP image, actual nginx image and installed
  Caddy 2.11.4 binary**. It used synthetic requests, no live mounts/credentials,
  a separate loopback-only TLS fixture, no pulls and no normal app entrypoint.
  Both public TLS and internal HTTP forwarded-header spoofing were rejected.
- All three real HTTPS endpoints returned 200 before maintenance. The existing
  configured MMS API credential returned 403 `Invalid token`; that failure was
  explicitly recorded as the pre-existing baseline, not waived as healthy.
- Source migration filenames were compared to the current ledger: **zero
  pending application source migrations** before recreation.
- The production-specific temporary Ansible playbook passed `ansible-lint`,
  `yamllint`, syntax check and protected `--check --diff`:
  **`ok=20 changed=5 unreachable=0 failed=0 skipped=0`**. Live Compose diffs and
  secret-bearing results were suppressed; only safe nginx source diffs were
  shown. The exact-host and recovery-checkpoint gates were enforced.

## Fresh checkpoint and recovery gate — passed before configuration apply

The retained checkpoint is:

`/opt/backups/football-club/pre-proxy-hardening-20261029T054057Z`

It is root-owned **0700**, with regular files **0600**. It contains original
Compose/nginx files, a private `.env` copy, container/config/Caddy/schema
baselines, the fresh SQL/storage/public snapshot, checksums, private startup
logs and reviewed one-off operations under `operations/`. **Never commit,
upload or print its contents.** No backup payload left production.

The scheduler and both queue workers were drained gracefully, then only Invoice
Ninja was stopped for a coherent snapshot. The backup used supported
`mariadb-dump` with existing credentials inside the DB container, not the broken
nightly `mysqldump` job and not a password literal on the command line.

Before configuration apply was allowed:

| Recovery gate | Actual result |
|---|---|
| Fresh DB dump completion/compression | Passed |
| Isolated fresh DB restore | **79 tables** restored; `mariadb-check` passed |
| Restore engine | Exact existing production MariaDB 12.3.2 image; network none, no ports, tmpfs data, 768 MiB/one CPU; event scheduler explicitly off |
| Storage payload restore | **6 regular files** extracted privately and hash-checked |
| Public payload restore | **1,616 regular files** extracted privately and hash-checked |
| Archive links | Two public links retained as archive metadata, deliberately not followed into live paths |
| Artifact hashes and private permissions | Passed; rechecked after rollout |

The restore database never mounted or overwrote live data. Temporary restore
data/containers were removed. This verified one-off checkpoint does **not**
repair or certify the daily/offsite backup workflow or other-service recovery.

## Apply and service recreation

The same temporary operational playbook applied exactly five configuration
changes with **`ok=20 changed=5 unreachable=0 failed=0 skipped=0`**. A private
normalized before/after Compose comparison allowed only the four named Invoice
Ninja environment fields and nginx command; all remaining settings compared
equal. Both installed nginx files matched the VM-verified source hashes.

Only the two approved services were recreated:

```bash
docker compose -p football-club -f /opt/football-club/docker-compose.yml \
  --env-file /opt/football-club/.env up -d --no-deps --pull never invoiceninja nginx
```

Invoice Ninja and nginx started at **06:01:41 UTC**. First healthy/local login
200 was confirmed at **06:01:52 UTC**. The conservative interval from beginning
worker drain to first healthy/local HTTP 200 was **78.9 seconds**, including
the coherent backup/recovery gate and apply. This is the measured maintenance
interval, not a claim about each external client's exact outage duration.

Startup reported **“Nothing to migrate”**. The protected startup capture had
zero PHP-fatal/uncaught/SQLSTATE lines. Prepared paired rollback was not needed.

## Post-apply acceptance and independent audit

| Check | Result |
|---|---|
| Effective Laravel configuration | Debug **false**, trust **`127.0.0.1,::1`**, stack logging, PHP **8.4.27** |
| Actual application URL generation | `https://billing.fkcesis.lv/client/login` |
| Public Caddy TLS request with spoofed forwarded headers | Login 200; actual loopback probe client IP **127.0.0.1** reached nginx normalization, instead of the previous bridge peer 172.18.0.1 |
| Internal MMS-container spoof probe | HTTP 200; nginx retained the actual container peer IP, not the forged address |
| Session-cookie security | Laravel session remained **Secure and HttpOnly** |
| Active HTTPS routes | Billing login, Docuseal root and MMS health all **200** with normal certificate validation |
| Actual logger under UID 33 | Benign synthetic warning found in the normal application log; debug remained false |
| No-token API error | Expected 403 `Invalid token`, without trace/exception/file/line fields or attacker hostname |
| Existing MMS credential | **403 `Invalid token` before and after**; credential issue persists, not a proxy regression or green integration |
| Synthetic PDF | **16,121 bytes**, valid `%PDF-` magic; separate accepted-image container, no network, app bootstrap or real invoice |
| Process state | FPM, both queue workers and scheduler RUNNING; no forced jobs |
| Schema/migration ledger | Normalized schema and migration-record hashes unchanged, including final audit |
| Images | All eight running image identities unchanged; accepted PHP-hotpatch pin retained |
| Other six containers | IDs, image IDs and start times unchanged through final audit |
| `.env` and Caddy | `.env` bytes/permissions unchanged; Caddy file hashes, active JSON, PID and active-start timestamp unchanged |
| Cleanup | All synthetic proxy/restore/archive containers and fixture networks gone; temporary production workspace removed |

No public diagnostic endpoint was installed. Authenticated browser login and
real invoice/mail/payment flows were not exercised; no test sends or payment
actions were deliberately triggered. Ordinary workers resumed once for normal
operation.

## Repository verification

- **109 focused contracts passed, no skips:** 11 deployment-security checks and
  98 existing PHP-hotpatch/image-selection checks.
- Repository `ansible-lint roles playbooks tests`, YAML lint and both site and
  validation playbook syntax checks passed. The scoped production playbook's
  own lint/syntax/check-mode/apply results are recorded above.
- Full discovery ran **222 test methods**, retaining **53 pre-existing
  failure/subtest entries**, zero errors and zero skips. The full suite is not
  green and those failures were not silently waived.
- Markdown evidence was updated instead of regenerating historical HTML. No
  commit, push or unrelated cleanup was performed during production maintenance;
  committing its reviewed repository changes is a separate operation.

## Retained rollback procedure — prepared, not executed

Review the private helper and current state before any rollback decision:

```bash
sudo -n env FK_PROXY_BACKUP=/opt/backups/football-club/pre-proxy-hardening-20261029T054057Z \
  python3 /opt/backups/football-club/pre-proxy-hardening-20261029T054057Z/operations/prod-proxy-activate.py rollback
```

It guards host/image identities, unchanged `.env` and absence of newer config
edits, restores the paired previous Compose/nginx configuration and recreates
only the two services without pulling. Debug stays false and PHP stays 8.4.27.
It does not restore a database or remove volumes. **Rollback reintroduces
wildcard proxy trust** and is incident recovery, not an approved steady state.
No live rollback was executed or claimed tested here; fresh backup recovery
was actually tested before apply. No backups/images/volumes were pruned.

## Still open

1. **MMS Invoice Ninja credential repair:** the existing key is rejected. This
   approval did not permit creating/rotating/replacing it. Repair and retest
   separately without exposing credentials in chat or committing plaintext.
2. **Deferred to `server-backups`:** routine daily/offsite backup work is handled
   by that separate project per user direction (2026-10-29). Historical failures
   concern only the legacy repo-managed job, which was not altered or removed.
   External coverage was not audited here. One-off deployment checkpoints and
   their recovery verification remain part of safe maintenance in this repo.
3. **Image maintenance:** the observed production images remain unchanged and
   mostly configured through mutable tags. Reviewed per-inventory pins, scanning
   and the official Invoice Ninja migration evaluation remain separate work.
4. **Regression baseline and isolation:** the known legacy full-suite failures,
   broader shared-network/FastCGI isolation and business-flow coverage are not
   fixed or waived by this rollout.
