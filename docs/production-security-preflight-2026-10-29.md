# Production security preflight — read-only, 2026-10-29

**Historical pre-rollout snapshot:** the user subsequently approved the scoped
backup-gated production fix. It was applied and verified later on 2026-10-29;
see the [completed production rollout](production-proxy-rollout-2026-10-29.md)
for current proxy/debug/logging state, the open credential issue and the deferred
legacy-backup findings.
The observations and unexecuted proposal below describe the earlier read-only
phase, not a claim that the later approved rollout did not occur.

**Daily-backup ownership clarification, 2026-10-29:** the user confirmed that
routine daily backups are handled by `server-backups` and deferred that work
here. The findings below concern only the legacy repo-managed `backup.sh` job,
not the external project's coverage. No legacy job was disabled or removed,
and this inspection did not audit `server-backups`.

## Decision and authorization boundary

**Read-only inspection completed. No production change is authorized or applied
by this report.** The VM-tested proxy fix is structurally compatible with the
observed production ingress. Production still uses wildcard proxy trust, and
its scheduled backups are unusable. Do not restart services until a fresh
private checkpoint has passed the proposed recovery gate and the user has
explicitly approved the scoped maintenance below.

This is a dated observation and rollout proposal, not executable configuration,
image approval, a vulnerability scan or proof of successful production rollout.
The source of truth remains role templates/defaults and inventory overrides,
plus independently checked host state. Do not copy this snapshot over future
runtime/configuration changes without reinspection.

## Inspection performed

At approximately **2026-10-29 05:14 UTC**, the inventory target
`deploy@netcup-prod-1.tail45ce0a.ts.net` was confirmed as actual hostname
`netcup-prod-1`, project `/opt/football-club`, Compose project `football-club`.
The running Invoice Ninja native image matched the production inventory pin
before private configuration inspection was allowed to proceed.

Only SSH/read commands, Docker inspection, version-only CLI invocations,
existing-log aggregation, Caddy **adaptation** and one read-only loopback Caddy
admin `GET /config/` were used. Active Caddy JSON matched the adapted on-disk
configuration exactly; its body stayed in host memory and was not printed.
No admin load/reload/write request was made. The PHP checks
read selected environment/static configuration fields with `php -n`; they did
not bootstrap Laravel. No Ansible apply/check-mode task was run on production,
no public/application HTTP/API request was issued, and no database query, backup execution,
restore, image pull, test-container creation, restart, credential change or
configuration write was performed. No Vault file was read or decrypted.

Configuration bodies, complete environment/inspect dictionaries, existing logs,
SQL and backup contents were not printed or transferred. Compose interpolation
and selective parsing stayed in host memory. Normal SSH/Docker audit logging
was not disabled.

Before/after checks during inspection confirmed:

- All **8 running containers** retained their IDs, image IDs and start times.
- Compose, `.env`, nginx and present Caddy configuration file hashes matched.
- Caddy's service PID and active-start timestamp matched.

## Host and ingress compatibility

| Item | Observed production state |
|---|---|
| OS | **Debian GNU/Linux 13 (trixie)**, not the Ubuntu VM's host OS |
| Docker | 29.8.1; AppArmor/seccomp/cgroup namespace security options; no rootless option reported |
| Caddy | 2.11.4, matching the VM's installed Caddy version |
| Disk and memory headroom | Approximately 221.81 GiB free disk and 4.8 GiB available RAM; 4 logical CPUs. Recheck before maintenance. |
| Billing routing | `billing.fkcesis.lv` -> host Caddy -> `127.0.0.1:8089` -> nginx |
| Caddy trust/header overrides | No trusted-proxy configuration observed; only `X-Request-Id` was explicitly set on the billing proxy route |
| Active Caddy configuration | Read-only admin GET matched the adapted on-disk configuration, including the billing/trust summary |
| nginx ingress | One IPv4 default route through **172.18.0.1**, on `football-club_default`; do not copy the VM's different gateway |
| nginx binary | **1.31.2**, compiled with `--with-http_realip_module` |
| Existing access-log sample | 131 access entries parsed from the last 200 log lines; all 131 had the default gateway as nginx's peer. No URLs, real client addresses or request bodies were exposed. |
| Published application ports | nginx 8089, Docuseal 3039 and MMS 8019 remain bound to 127.0.0.1; databases, Redis and PHP-FPM have no host-published ports |

The gateway-based normalization approach has evidence on the actual production
ingress without generating an application probe request. However, existing access logs do
not prove post-fix request behavior. The production spoofing/HTTPS/API checks
remain post-approval acceptance work. Do not run the whole Ubuntu-oriented
stack playbook on this Debian host merely because the VM passed.

The proposed narrow edit shape was checked read-only: one debug field, one
trusted-proxy field and one folded nginx command block. The new startup script,
host-proxy include, real-IP directives and forwarded-header stripping are not
already present on production. The guarded patch can therefore target the
original configuration rather than overwrite an unknown partial installation.
The existing Laravel nginx file and normalized nginx command also matched the
original repository baseline at commit
`16f364f16f5c7d49b734ea7a1eff05d39c7c5ff9`; no custom production edits were found
in those two replacement targets. Reconfirm that match before applying.

## Invoice Ninja debug and trust findings

- **Debug is already disabled**, not newly found enabled: Compose and container
  environment both select `APP_ENV=production`, `APP_DEBUG=false` and
  `APP_URL=https://billing.fkcesis.lv`.
- The running PHP CLI reports **8.4.27** and the image label is **5.13.26-d**.
  The accepted custom image must remain selected; no official candidate was
  pulled or substituted.
- There is no compiled Laravel configuration cache or in-container `.env`
  file. Static application configuration reads debug and proxy trust from
  environment values. No request/exception-page probe or Laravel bootstrap was
  executed under the read-only authorization.
- **`TRUSTED_PROXIES='*'` is still present** in Compose/container environment.
  nginx has neither the new real-IP normalization nor forwarded-header removal.
- Compose does not explicitly select `LOG_CHANNEL`/`LOG_LEVEL`. The proposed
  stack/warning settings preserve warning/error logging, but production log
  writing must be checked after the authorized rollout, not assumed from the VM.
- The host `.env` is mode **0600**. Its bytes were not changed or exposed.

The historical MMS API credential mismatch remains an **unretested limitation**
from the 2026-10-22 hotpatch evidence. This inspection made no authenticated API
call and queried no CompanyToken records. The sampled access entries did not
contain API requests, so they do not establish today's authentication status.
The proposed proxy change does not create, replace or rotate an API token.

## Observed running images — not new deployment pins

All observed images are `linux/amd64`. Every configured reference currently
resolves locally to the same native image ID used by its running container;
no cached-tag drift was found. Recheck that equality immediately before an
approved recreation. Versions below come from the running binary where
available, with image labels used for Invoice Ninja's app version.

| Component | Version / identification | Configured reference |
|---|---|---|
| Invoice Ninja | App label 5.13.26-d; PHP CLI 8.4.27 | Accepted host-native `sha256:` inventory pin |
| nginx | Binary 1.31.2 | `nginx:alpine` |
| MariaDB | Binary **12.3.2** | `mariadb:lts` |
| Redis | Binary 8.8.0 | `redis:alpine` |
| PostgreSQL | Binary 18.4 | `postgres:18-alpine` |
| Docuseal | Exact image known; application semver not established by image labels. Ruby binary is 4.0.5, **not the Docuseal version**. | `docuseal/docuseal:latest` |
| MMS web and worker | Same exact image; no app-version/revision label reported | `ghcr.io/linards-kalvans/fk-cesis-mms:main` |

Observed immutable identities, recorded as a dated audit snapshot:

```text
Invoice Ninja native ID:
sha256:b8e368e6fa68c2a715d0100455f06e17827d4652398c63e2fcaed092f2b0632e

nginx:
nginx@sha256:54f2a904c251d5a34adf545a72d32515a15e08418dae0266e23be2e18c66fefa

MariaDB:
mariadb@sha256:628f228f0fd5913a220438693576b29b6fe4dc1fa0a1298c0e98579fae28635f

Redis:
redis@sha256:9d317178eceac8454a2284a9e6df2466b93c745529947f0cd42a0fa9609d7005

PostgreSQL:
postgres@sha256:1b1689b20d16a014a3d195653381cf2caa75a41a92d93b255a9d6ea29fd353aa

Docuseal:
docuseal/docuseal@sha256:b585c37656c1e85ead752f8597e1149caf666894f50d7a91e49881cceb5562de

MMS web and worker:
ghcr.io/linards-kalvans/fk-cesis-mms@sha256:f7db2808b8b57ca7ce1c4fa97e7981b1175c7cb080cb05f0380b1838fa3b94ca
```

The registry references above are actual reported `RepoDigests`, not invented
by attaching a repository name to a native ID. The custom Invoice Ninja image
has **no RepoDigest**: keep its existing native pin and the previously verified
source/native identity mapping. Do not turn that ID into a made-up registry
reference or replace it with the different source config digest.

**Production MariaDB is 12.3.2; the VM's tested MariaDB was 11.8.6.** Never copy
a VM database image selection into production as part of pinning. A downgrade
is not a compatibility-preserving pin. Likewise, do not pull current upstream
`lts`, `latest`, `main` or Alpine tags as part of this proxy change. Converting
these observations into reviewed per-inventory pins and establishing image
scanning remain separate repository work; no pin was changed here.

## Backup readiness — confirmed blocker

The deployed `/opt/football-club/backup.sh` is scheduled by root cron at
`0 2 * * *`, but calls **`mysqldump`**, which is absent from the running MariaDB
container. `mariadb-dump` is available. The deployed script also contains the
placeholder **`offsite-host`**, uses a floating Alpine helper and does not set
a restrictive `umask 077`.

The three latest scheduled directories were inspected without opening SQL or
archive payloads:

| Directory | Invoice Ninja SQL | Remaining expected service archives/dump |
|---|---|---|
| `20261029_020001` | **0 bytes** | Missing |
| `20261028_020001` | **0 bytes** | Missing |
| `20261027_020001` | **0 bytes** | Missing |

These directories are 0755 and the empty SQL files 0644, under a 0750 backup
parent. They do not follow the private-checkpoint policy. Ancestor permissions
still matter; this is not evidence that credentials or database rows leaked.
The decisive issue is that these are not usable service backups.

The earlier root-private checkpoints remain present:

- `pre-php8427-20261022T105907Z`
- `pre-php8427-quiesced-20261022T110934Z`

Both directories are 0700 and their regular files are private. They are dated
2026-10-22, not a fresh rollback point. Prior restore results are historical
evidence in the hotpatch runbook; their contents were **not** restored or
re-certified by this read-only inspection. No existing backup was changed,
deleted, exported or pruned.

Repairing the daily workflow requires the supported dump command, fail-closed
artifact validation, private permissions, reviewed helper identities and a real
offsite destination/access arrangement. That repair is separate from the
proposed scoped hotfix. A fresh independently verified private checkpoint can
gate the hotfix, but does not make daily/offsite backup automation healthy.

## Exact proposed production maintenance — NOT executed

### 1. Reconfirm scope and pass the backup gate

After explicit user approval, guard the exact production SSH identity/hostname,
project path, original application pin and observed nginx identity above.
Recheck file hashes, all eight container fingerprints, resource headroom and
cached-image equality. Refuse concurrent drift rather than overwrite it.

Record a read-only baseline of login, cookie behavior and authenticated MMS API
status without printing credentials or response bodies. The old credential
mismatch must be retested, not assumed fixed or newly blamed on this patch.
Do not repair credentials under proxy-only approval.

Before any service recreation, confirm there are **zero pending application
source migrations** against the current ledger. If not, stop: permission for
a proxy restart does not authorize schema changes or migrations.

Reserve a maintenance window for application quiescence, backup/recovery and
startup checks. Gracefully drain Invoice Ninja's scheduler and both queue
workers, then stop only Invoice Ninja to take a coherent checkpoint. If a
pre-apply check fails, resume the original service/configuration and halt.

Create a root-owned 0700 checkpoint, files 0600, including current Compose/nginx
files, private `.env`, DB/storage/public data and schema/migration/container
baselines. Validate hashes, compressed data and SQL completion. Actually restore
the **fresh** DB dump into an isolated, network-none, no-published-port tmpfs
container using the exact production **MariaDB 12.3.2 image**, then run table
count/integrity checks. Use bounded resources (for example 768 MiB, one CPU)
and recheck free memory first. Verify private storage/public restore payloads
without following archive links into live paths. No live database restore,
new database major, registry pull or offsite placeholder execution is permitted.

This creates private backups and disposable restore resources on production;
those are **future write operations requiring approval**, not part of this
completed read-only inspection.

### 2. Apply only the VM-tested proxy/logging change

Use a reviewed production-specific operational playbook, not the VM-host-guarded
helper or the whole-stack role. Run protected syntax/lint and `--check --diff`
before apply. Suppress sensitive Compose/env output; never decrypt Vault for
this operation or rewrite `.env` just to apply the proxy fix.

Allowed changes only:

1. Keep debug false as an explicit environment string; add `LOG_CHANNEL=stack`
   and `LOG_LEVEL=warning`.
2. Replace Laravel wildcard trust with `127.0.0.1,::1`.
3. Select nginx's reviewed startup script.
4. Install the exact reviewed `start-nginx.sh` and Laravel nginx configuration
   already verified on the VM, deriving the production gateway dynamically.

Privately compare normalized before/after Compose models, permitting only the
four named Invoice Ninja environment fields and nginx command. Image choices,
credentials, volumes, networks, published ports, other commands and services
must compare equal. Preserve the host-owned Caddy main file and imported routes.

Only after quiet Compose validation and the safety checks may the two services
be recreated, without dependency starts or pulls:

```bash
# PROPOSED ONLY — requires explicit maintenance approval and the gates above.
docker compose -p football-club -f /opt/football-club/docker-compose.yml \
  --env-file /opt/football-club/.env up -d --no-deps --pull never invoiceninja nginx
```

This interrupts Invoice Ninja/nginx temporarily. The six other containers
(MMS web/worker, PostgreSQL, MariaDB, Redis and Docuseal) must not restart.
Do not invoke MMS startup/migrations, update images, change network/volume
definitions, rotate credentials or alter database schemas.

### 3. Verify and retain evidence

Bound application readiness polling to 180 seconds, with a prepared paired
configuration rollback. Include backup/check time in the maintenance window;
180 seconds is not a guaranteed total interruption duration.

Require effective debug false, correct proxy trust/logging, nginx config
validation, unchanged image identities and normal FPM/worker/scheduler state.
Check public TLS login, cookie security, generated HTTPS URLs and hostile
forwarded headers on both host-Caddy and internal MMS paths. Recheck the
authenticated read-only MMS API against its baseline; do not print tokens or
response bodies, create invoices, force jobs or send test mail/payments. A
pre-existing 403 is not fixed or green merely because it remains a 403.

Verify warning/error logging with a benign marker and no debug trace returned
to clients. Recheck `.env` bytes, Caddy hashes/PID, normalized schema/migration
hashes and all six unaffected container identities/start times. Keep private
startup/recovery evidence on the host, and remove only disposable resources
created by this maintenance. Do not prune images, volumes or old backups.

### 4. Paired rollback

Restore the checkpoint's **paired** Compose command/environment and nginx
configuration; remove the new startup script only if it did not previously
exist. Guard unchanged `.env`, accepted image identities and absence of newer
configuration edits before restoring. Recreate only the same two services with
`--no-deps --pull never`. Never use `down -v`, downgrade PHP/database images,
change credentials or restore over a live database for this config-only patch.

Rollback restores wildcard proxy trust and is incident recovery, not a secure
steady state. Debug must stay false. No production rollout or rollback was
rehearsed/executed during this inspection; the protected current checkpoint and
operator approval must exist first.

## Verification limits and remaining work

- Inspection assertions passed, including exact host/image guards and no
  configuration/container/Caddy drift during the main collection.
- No application HTTP/exception/authentication test, DB inspection/restore,
  image-layer vulnerability scan or runtime fixture was run. Static nginx
  capability and existing ingress logs are evidence, not post-change tests.
- No repository executable configuration changed in this preflight. Only
  documentation was updated; test-suite/Ansible deployment runs were skipped
  for this documentation-only step. The preceding VM pass and known 53
  pre-existing full-suite failures remain documented, not reclassified green.
- Backup automation/offsite repair, reviewed immutable service pins, legacy
  test repair, production API credential retest/repair and official Invoice
  Ninja candidate migration evaluation remain separate work.

**Approval requested, not assumed:** the backed-up, restore-gated two-service
proxy/debug/logging maintenance above. It does not authorize general stack
redeployment, image/database upgrades, credential rotation or backup-automation
changes.
