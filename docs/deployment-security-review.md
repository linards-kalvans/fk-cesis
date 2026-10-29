# Deployment security maintenance — 2026-10-28

## Status and scope

**Repository hardening is partial; the proxy/debug/logging fix is applied and
verified on both the VM and production.** The user explicitly approved the
backup-gated production change after its read-only preflight. Current results,
the proven 79-table recovery checkpoint and remaining credential failure
are in the [completed production rollout](production-proxy-rollout-2026-10-29.md).
This is not a blanket approval for other production changes. Exact pre-change
image identities and the original proposal remain in the historical
[production preflight](production-security-preflight-2026-10-29.md).
Per user direction on 2026-10-29, routine daily/offsite backup work is deferred
to the separate `server-backups` project. Legacy-job findings below are retained
as evidence about this repo's old `backup.sh`, not a conclusion that server-wide
backup coverage is absent or a daily-backup remediation task here. That external
coverage was not audited by this work. One-off deployment recovery gates remain.
Topology evidence and remaining threat-boundary limitations are documented in
[Invoice Ninja proxy hardening](invoiceninja-proxy-hardening.md). The starting checkout had
substantial staged and unstaged changes; they were preserved. No Vault contents
were read or decrypted. No application image identities, database major
versions, volume definitions, credentials, ports or scheduled-backup definitions changed.
The VM follow-up recreated only Invoice Ninja/nginx and restored private backup
copies into isolated temporary targets, never over live data. Production
subsequently received only the approved two-service proxy/logging change.
`.env` bytes were preserved on both hosts, as were all 13 unrelated VM containers
and all six unaffected production containers. No image identity or live schema changed.

This bounded change strengthens debug validation, explicit environment types,
implicit image refresh and missing security CI. The follow-up also fixes the
demonstrated HTTP forwarding trust flaw locally, on the VM and in production,
with scoped Invoice Ninja backup/restore verification. Credential integration,
mutable-image conversion, broader network isolation, other-service recovery
exercises and an Invoice Ninja migration
remain separate release-gated work. Use `pm-arch` for that coordinated follow-up;
do not treat this report as having executed it.

## Confirmed findings and false positives

| Finding | Current evidence and disposition |
|---|---|
| Production debug enabled | **Already false by default before this review**, through a pre-existing working-tree change. Overrides could still enable debug. The template now emits an explicit string; a first-task assertion rejects debug before rendering or starting anything. `APP_ENV` is always production in both inventories, so neither permits debug. |
| Boolean environment compatibility | The former debug expression and `REQUIRE_HTTPS: false` were YAML booleans, but **Compose 2.40.3 successfully validated the original boolean forms too**. This is not a demonstrated Compose failure. Quote them for explicit environment strings, preserving the existing HTTPS flag's false semantics rather than changing routing blindly. |
| Wildcard proxy trust | **Confirmed, reproduced, fixed and verified on both VM and production**. Tests cover accepted images/actual host binaries and both ingress paths. nginx normalizes CGI from its own bridge-gateway ingress and removes supported forwarded headers; Laravel trusts loopback only. Production's pre-existing MMS credential rejection remains separately open. |
| Floating images | **Confirmed, not fully remediated**. Known mutable references are explicitly baselined in tests; new unexpected floating references fail. Existing references still need accepted host digests. |
| Silent application refresh | MMS images were pulled on every role run, and `up -d` could pull missing images. Pulling MMS is now opt-in; stack startup and the storage initialization helper use `--pull never`. This does not make cached mutable tags immutable. |
| Historical Codeberg and Octane descriptions | **Outdated**. Active MMS defaults select GHCR; Invoice Ninja uses the Debian PHP-FPM image and separate verified inventory IDs. AGENTS and README now describe that distinction. Historical specs are not current image selections. |
| Invoice Ninja application lag | Historical evidence identifies production as 5.13.26-d with PHP 8.4.27; live state was not rechecked. Current public candidate metadata identifies 5.13.50-d with PHP 8.5.12. Not approved for deployment. |
| Secret scanner finding | Initial Gitleaks scan flagged the literal documentation placeholder `YOUR_API_TOKEN`, not a live credential. Replaced it with a shell environment reference; the subsequent redacted scan found no leaks. This is a current-tree scan, not proof of a clean Git history. |

`LOG_CHANNEL=stack` and `LOG_LEVEL=warning` preserve warning/error logging while
debug stays off. A local accepted production-source image successfully wrote a
synthetic warning to its temporary Laravel log with these exact settings, PHP
8.4.27, no network and no normal entrypoint. Its log filesystem was disposable.
Live log permissions, cached Laravel configuration, error-page sanitization and
log rotation/access controls still require operator verification. Logs themselves
can contain sensitive context; do not publish them as CI artifacts.

## Proxy topology and initial trust-boundary findings

This section records the **pre-fix** investigation. For the implemented local
fix, test evidence and remaining host acceptance gates, the linked
[proxy hardening follow-up](invoiceninja-proxy-hardening.md) takes precedence.

Executable templates describe:

```text
Internet -> host Caddy (TLS) -> 127.0.0.1:8089 -> Docker nginx:80
                                                  |
                                             FastCGI :9000
                                                  |
                                              Invoice Ninja

MMS web/worker --------> nginx:80 /api/v1  (shared default Docker network)
Docuseal, databases and cache also share that default network.
```

The public binding is loopback-only, but not container-isolated. Nginx includes
`fastcgi_params`, sets `SCRIPT_FILENAME`, and forwards to Invoice Ninja. It has
no explicit forwarded-header sanitization or `real_ip` policy. There are no
static addresses or custom networks in the current Compose model.

For public requests the application needs the original HTTPS scheme, original
billing host and real client IP from Caddy. Internal MMS requests use HTTP and
the internal nginx hostname, so forcing all requests to a public HTTPS host
without testing can break that integration. Caddy normally sets/sanitizes
`X-Forwarded-For`, `X-Forwarded-Proto` and `X-Forwarded-Host`, but both inventories
set `football_club_manage_caddy: false`: the actual host-owned main Caddyfile,
imports, upstream trusted-proxy settings and installed version are unverified.
Ansible manages only an imported snippet when explicitly enabled, never the
whole main file.

`TRUSTED_PROXIES='*'` lets all request peers influence supported forwarded
headers. A peer on the shared Docker network can bypass the public Caddy route.
This creates a plausible spoofing path; this review did **not** demonstrate a
remote exploit, or verify which header bitmask the running application uses.
Do not equate loopback publication or Caddy defaults with a complete fix.

**Required follow-up before claiming proxy hardening:**

1. Read the actual Caddy routes and application `TrustProxies` implementation
   for the accepted image. Record the FastCGI `REMOTE_ADDR` and relevant headers
   using synthetic requests in an isolated clone, not publicly exposed diagnostics.
2. Separate the proxy/application path from unrelated services; account for
   required MMS-to-nginx API access. Select deterministic proxy identity only
   after checking host subnet conflicts and FastCGI address semantics.
3. Sanitize forwarded headers at the verified ingress, strip alternate
   `Forwarded`/forwarded host/port headers unless required, and restrict the app
   to that tested proxy identity. Do not trust an entire shared bridge subnet.
4. Test malicious `Forwarded`, `X-Forwarded-For`, `X-Forwarded-Host`,
   `X-Forwarded-Proto`, `X-Forwarded-Port` from both public and internal paths.
   Verify real client IP, generated HTTPS links, billing host, login/session
   cookies, client portal, PDF links, authenticated API and MMS routing.

The follow-up replaces wildcard trust and verifies normal HTTP spoof resistance
locally without a topology change. Host validation and full application tests
remain deployment gates; broader container-compromise isolation remains separate.

## Image inventory and reproducibility policy

The executable source of truth is role defaults + inventory overrides + Compose
templates. Runtime truth must additionally be obtained from the host. Do not
duplicate host-selected image IDs into prose or copy candidate digests into
inventories without acceptance tests.

Public registry metadata was checked on 2026-10-28 without pulling application
layers. These are **upstream observations, not running versions or approvals**:

| Compose reference | Current public linux/amd64 metadata | Update policy |
|---|---|---|
| Invoice Ninja inventory `sha256:` IDs | Retained; existing host-specific approval tests pass | Keep verified native IDs and archive/provenance, or an accepted registry digest. Never substitute a source config digest for a Docker 29 native ID. |
| `docuseal/docuseal:latest` | Ruby 4.0.9; metadata does not establish Docuseal app version | Record app version from isolated runtime, back up SQLite and `/data`; pin accepted digest after restore test. |
| `mariadb:lts` | **12.3.3** | Do not pull this as a routine refresh. Record running major first: `lts` can cross majors. Pin the accepted existing major/patch plus digest; test database backup and restore. |
| `redis:alpine` | 8.10.3 | Record current major and persistence format; test cache, sessions, queue and restored data before pinning. |
| `nginx:alpine` | 1.31.8 | Pin reviewed version plus digest after config and FastCGI/proxy tests. |
| `postgres:18-alpine` | 18.6 | Stay on major 18; preserve `/var/lib/postgresql` mount. Test dump/restore and MMS migrations separately. |
| GHCR MMS `main` / VM `dev` | Private/current running digest not obtained | Pin the reviewed build digest for both web and worker together; do not restore historical Codeberg defaults. |
| Task helper `alpine:3.20` | Not inventoried as a running service | Also needs an accepted digest; now preloaded-only. |
| Host Caddy | Not a Compose image | Record installed package version and host configuration separately. |

Current public index digests (observation only; **do not deploy these as a bulk
upgrade**):

- Docuseal: `sha256:2786607f1f6eb54f982a926bd78c81ee23b6545e59d1ff548bd672094760621c`
- MariaDB: `sha256:d46e102fa8b9b72bfcdeb56f9dd538742092119dc8b11f31fe662605cd234cd9`
- Redis: `sha256:47b08295737773de3b711fb86f13ae802f5074e96a9a2d29f5f80164ac08c046`
- Nginx: `sha256:a3554c0d0b48177b1413c26e01f695334428020d9df01243fbae3e11cfd17417`
- PostgreSQL: `sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5`

Registry observations come from the [Docker Hub tag API](https://hub.docker.com/v2/repositories/)
and authenticated public [registry API](https://registry-1.docker.io/v2/).

### Required image acceptance/update workflow

Owner: deployment maintainer. **Review the remaining mutable-image exceptions
and proxy blocker by 2026-11-04**, then review weekly and immediately for relevant
critical advisories. The review date is an operational follow-up, not a test
that silently expires or a risk acceptance.

1. With separate authorization, collect only service name, configured image,
   container `.Image`, image ID, platform, `RepoDigests` and app/runtime versions.
   Use `docker compose ps -q`, `docker inspect --format '{{.Image}}' CONTAINER`
   and `docker image inspect --format '{{.Id}} {{json .RepoDigests}}' IMAGE`.
   Do not dump container environments or complete inspect JSON to reports.
2. Preserve accepted image archives and rollback evidence. Record upstream
   version, platform/index/child digest and review date alongside the change.
   A public tag digest discovered today is not necessarily the running digest.
3. Review release notes, application and OS/runtime advisories, scan accepted
   images by immutable identity, and record exceptions with owner, reason and
   next review date. No blanket CVE suppression or automatic major upgrades.
4. Restore synthetic or appropriately protected backup data into an isolated
   VM; disable real mail, billing sends, webhooks and worker side effects. Run
   application/API/PDF/queue tests and manual backup/restore validation.
5. Submit the version/digest change for review. Use `repository:version@sha256:…`
   where practical. The current MMS template appends `:tag`; digest support
   needs a coordinated template change rather than appending a digest blindly.
   Remove the corresponding known-floating test exception when converted.
6. Preload all accepted images, including the initialization helper, before
   first startup. Ordinary Ansible runs now fail instead of implicitly pulling
   absent images. Existing cached mutable tags can still drift if another
   operator pulls them; digest conversion remains necessary.
7. MMS refresh now requires `football_club_stack_pull_mms_images=true`, and
   explicit approval in production. This switch alone is not image approval.

## Invoice Ninja upgrade evaluation

The [latest upstream application release](https://github.com/invoiceninja/invoiceninja/releases/tag/v5.13.50)
was v5.13.50, published 2026-10-21. Its notes include dependency updates and API
fixes. Review the [full application delta](https://github.com/invoiceninja/invoiceninja/compare/v5.13.26...v5.13.50),
including migrations and Composer changes, before accepting a candidate.

The [official Debian latest metadata](https://hub.docker.com/v2/repositories/invoiceninja/invoiceninja-debian/tags/latest)
resolved to index
`sha256:a441339c959b7e8e8a9f346dd4eff2759f0f39a87a5b3eff875c465fbca1566b`;
amd64 manifest
`sha256:0f04fd7e8a0b6202c65a1d193d16dc4ca7ca20161c388b9af0a784a8684e10c1`;
config
`sha256:ddaeda7a8914644e151d302dd1a1c6c73dae98174d57e3309641cab0ac8282f4`.
The config reports application label **5.13.50-d** and `PHP_VERSION=8.5.12`.
This is metadata evidence, **not an executed runtime or extension check**.
It crosses from PHP 8.4 to 8.5 and is therefore not a drop-in patch acceptance.

The [PHP 8.4.27 release metadata](https://www.php.net/releases/index.php?json&version=8.4.27)
confirms the security release and source SHA256 used by the existing hotpatch.
[PHP 8.5.12 metadata](https://www.php.net/releases/index.php?json&version=8.5.12)
also marks a security release. That alone does not verify the image's binaries,
extensions or application compatibility; retain the current complete rebuild of
bundled modules until equivalent runtime/source verification is done.

Published application advisories returned by the upstream security API were
[CVE-2026-33742](https://github.com/invoiceninja/invoiceninja/security/advisories/GHSA-xph7-9749-56mh)
and [CVE-2026-33628](https://github.com/invoiceninja/invoiceninja/security/advisories/GHSA-98wm-cxpw-847p),
both stored-XSS advisories fixed in 5.13.4. The documented current production
application version is newer than that fixed version; these are not evidence
that 5.13.26 is vulnerable. Conversely, two published advisories and newer release
notes are not a complete dependency, OS, Chromium/PDF or image security audit.
Outstanding security differences beyond PHP have not been comprehensively
enumerated; scan and compare both exact images and Composer locks next.

**Recommendation: retain the verified PHP 8.4.27 custom images temporarily.**
Do not overwrite either inventory pin. Reassess by 2026-11-04. Approval of an
official image requires an isolated DB restore/migration, startup/config cache
checks, actual `php -v` and extension versions, real sanitised-error/logging
checks, PDF generation, queue/scheduler execution with external sends disabled,
login/client portal and authenticated MMS/API integration tests. This review ran
only the existing pin/smoke-script contracts and a local logging probe, **not**
the official candidate's migrations or application smoke. Existing documented
production API credential mismatch is still outside this change; no secrets
were rotated.

## Automated checks and limitations

`.github/workflows/security.yml` adds PR/main, weekly and manual validation with
read-only repository permissions and no deployment credentials:

- Render both real non-secret inventories with role defaults and strict Jinja;
  validate Compose using synthetic environment values and `config --quiet`.
- Reject debug overrides; check logging, explicit image refresh, expected image
  repositories, known mutable exceptions, loopback ports and existing database,
  Docuseal and Invoice Ninja volume/mount contracts.
- Run existing host-native Invoice Ninja image approval tests, Ansible lint,
  YAML lint and both playbook syntax checks without decrypting Vault.
- Run digest-pinned Gitleaks on the current tree with redaction (blocking).
- Run digest-pinned Trivy filesystem dependency/misconfiguration scanning with
  actionable report-only vulnerability findings. Scanner operational failures
  still fail. Manual input accepts an immutable registry image for remote
  container vulnerability scanning; no daemon socket or registry secrets are
  exposed. Host-local custom images need local/operator scanning; CI cannot
  automatically fetch those IDs. Manual scanning is not automatic coverage of
  every deployed image.

Observed Trivy source findings: **five high dependency findings** in local
`.opencode/package-lock.json` (`toml` 4.3.0: CVE-2026-114141 through -114144,
fixed in 5.0.1; `zod` 4.1.8: CVE-2023-54404, fixed in 4.6.6). These concern
development tooling, not proof of deployed application exposure, and are not
silently suppressed or automatically updated here. Tooling-owner review remains
open. Dockerfile findings DS-0002 (no non-root USER, high) and DS-0026 (no
HEALTHCHECK, low) need review against the retained upstream entrypoint/user
switching and runtime health behavior; do not add USER blindly to the verified
hotpatch recipe. Trivy did not render Jinja templates or scan application image
layers in that filesystem scan.

Checks executed locally:

| Check | Result |
|---|---|
| Eleven rendered security/startup/safety contracts | Passed, including both Compose models, proxy route rejection, remote-daemon and fixture-input guards, no skips |
| Existing Invoice Ninja hotpatch contracts | 18 passed, no skips |
| Full existing pytest baseline before edits | 200 passed, 53 failures (including subtests) |
| Full initial-pass system-Python unittest discovery | 218 test methods, 53 failure/subtest entries, zero errors/skips |
| `ansible-lint roles playbooks tests` from `ansible/` | Passed |
| `yamllint .` from `ansible/`, workflow YAML lint | Passed |
| Both playbook `--syntax-check` commands | Passed |
| Isolated local accepted-image logging probe | Warning log successfully written, PHP 8.4.27 |
| Gitleaks current tree | No leaks after fixing documentation placeholder |
| Trivy source scan | Executed successfully; findings above, not a clean bill of health |

The 53 full-suite failures remain: obsolete removed-service/Caddy/volume/Octane
contracts, missing expected old environment settings and Docuseal plan
assertions. They were present before this work; they are **not waived as safe**.
CI intentionally gates the focused current security contracts, not the obsolete
full suite. Do not report the whole suite as passing. Bare `pytest` uses an
isolated Python missing Jinja2; system Python has Jinja2/PyYAML but no pytest.
Use the documented system-Python unittest commands for the new contracts.

The follow-up ran local tests using both accepted source images, then the actual
VM Caddy/nginx/accepted PHP image, protected remote `--check --diff`, scoped VM
apply, real endpoint/authenticated read-only API/logging/error checks and
Invoice Ninja DB/payload recovery drills; see its separate evidence. Production
authenticated browser/business-flow tests, other-service restore certification
and official candidate runtime tests were not run. The later production phase
included read-only preflight, explicit approval, protected check/diff, scoped
apply, a fresh 79-table recovery test and live proxy/logging checks. The
production API credential returned 403 `Invalid token` before and after; it was
not repaired or relabeled healthy. The legacy daily job was not repaired;
routine daily/offsite backup work is deferred to `server-backups` as directed.
An unsanitized
`--diff` can expose existing secret-bearing templates: review locally, retain
`no_log` protections, and do not publish raw remote diffs.

## Proposed rollout and rollback (requires approval)

This lifecycle policy remains for future changes. The scoped proxy/debug/logging
rollout itself is already complete on the VM and production, as recorded above;
do not repeat it on the assumption that these general steps are pending.

1. Resolve the proxy and mutable-image blockers as separately reviewed changes.
   Snapshot the current effective configuration, approved images and backups
   privately. Verify restoration of active-service data before schema/image work.
2. On an isolated Ubuntu LTS VM, preload reviewed existing images, render with
   Vault via the normal protected operator workflow, run `--check --diff` with
   secret output controls, and apply. Validate all active endpoints and the
   malicious-header/login/API/PDF/logging checks above. Keep outbound sends off.
3. For this patch's config-only rollout, check `APP_DEBUG=false` in effective
   Laravel config (including any existing cache) and `.env` permissions; confirm
   errors are logged but details are not returned to unauthenticated clients.
   Do not run the role just to inspect debug: it starts the whole stack and MMS
   startup runs migrations. Scope any approved rollout carefully.
4. Request **explicit production approval** with the VM evidence, exact diff,
   unchanged image identities and service restart scope. Do not run production
   tasks or restart containers on the authority of this report alone.
5. Once approved, apply only reviewed configuration changes, validate and
   independently record the running image IDs and live effective settings.

Rollback this patch by restoring only its previous rendered config/task changes
and recreating only the approved affected services. Preserve all volumes and
credentials; never use `down -v`. **Do not restore debug=true.** Keep known-good
images locally so rollback does not require mutable-tag pulls. A future app or
database migration is different: an older image alone may not understand the
new schema; stop writers and restore the coordinated DB/storage backup if the
tested migration rollback requires it. Ordinary Ansible deployment is not a
safe rollback primitive when startup executes migrations.
