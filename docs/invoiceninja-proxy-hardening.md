# Invoice Ninja proxy hardening — VM and production verified, 2026-10-29

**Applied and verified on the VM (2026-10-28) and production (2026-10-29).** The
production change followed explicit user approval and a fresh, proven recovery
gate. See the [completed production rollout](production-proxy-rollout-2026-10-29.md)
and its remaining credential failure. Routine daily-backup work is deferred to
`server-backups`; the legacy-job findings are not an audit of that project's
coverage. The
[production preflight](production-security-preflight-2026-10-29.md) is the earlier
read-only snapshot. On each host, only Invoice Ninja and nginx were recreated.
No deployed image identities, credentials, volume definitions, published ports or live database schemas changed. The
original local investigation and the subsequent VM evidence are separated below.

## Root cause and reproduced behavior

The accepted production-source image contains Invoice Ninja's
`App\Http\Middleware\TrustProxies`, extending Laravel's middleware. Its mask
trusts `X-Forwarded-For`, `Host`, `Port`, `Proto` and AWS ELB headers, not RFC
`Forwarded`. Laravel interprets `*` as trusting the request's `REMOTE_ADDR`.

Crucially, nginx's original `fastcgi_params` passes the **HTTP client's address**
as `REMOTE_ADDR`, not nginx's own container address. Pinning the PHP trust list
to an arbitrary nginx IP therefore would not correctly describe this FastCGI
architecture.

Before changing the configuration, the local fixture reproduced an ordinary
container peer calling nginx (the same network path as MMS) and controlling the
framework's client IP, host, scheme and port using forwarded headers. It did
not need a raw socket, special capabilities, application login or database.
This confirms a request-metadata trust flaw; it does not claim a specific
unauthenticated Internet exploit or account takeover.

## Focused configuration change

```text
Host Caddy -> loopback publication -> Docker bridge gateway -> nginx
                                                              |
                         validate ingress, normalize CGI, strip forwarding
                                                              |
                                      PHP-FPM -> Invoice Ninja middleware

MMS/other container -> nginx -> ordinary HTTP CGI values, no forwarded trust
```

- `start-nginx.sh` discovers the **single IPv4 default-route gateway inside
  nginx's own network namespace**. It generates one exact trusted address,
  never a wildcard or a subnet. Missing/ambiguous routes fail before nginx is
  started. `nginx -t` also runs before startup. The existing UID 33 workaround
  is preserved.
- On the tested rootful Docker bridge, host connections to the loopback-published
  port arrive from that gateway. This was exercised through the real published
  port, not assumed from Docker's unrelated `host-gateway` alias or `docker0`.
- nginx's real-IP module accepts the last `X-Forwarded-For` address **only from
  that gateway**. Container peers cannot change their framework client IP with
  ordinary HTTP headers. `real_ip_recursive off` intentionally does not trust
  an arbitrary incoming chain.
- A map checks the original peer (`$realip_remote_addr`), not the rewritten
  client address, before accepting exactly `X-Forwarded-Proto: https`. PHP gets
  normalized `HTTPS`, `REQUEST_SCHEME` and `SERVER_PORT`; normal internal MMS
  requests remain HTTP on port 80.
- nginx removes the supported forwarded headers, RFC `Forwarded`, legacy
  forwarded SSL/server and `X-Real-IP` before PHP. The actual `Host`, cookie,
  Authorization and API-token headers remain intact. No Caddyfile ownership,
  external port, service network or volume definitions change.
- Laravel's wildcard is replaced with a valid **loopback-only** proxy list.
  It no longer interprets arbitrary request peers as proxies, and there is no
  forwarded-header chain left for it to re-interpret on the nginx path. This
  is not intended as the IP address of nginx.
- Changes to the startup script or Laravel nginx configuration notify the
  existing nginx restart handler, including on subsequent config-only updates.

Relevant upstream behavior:
[nginx real-IP module](https://nginx.org/en/docs/http/ngx_http_realip_module.html)
and [Caddy reverse-proxy header defaults](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#defaults).

## Executed tests and reproducible local harness

`tests/proxy_smoke.py` is an opt-in automated integration test. It uses:

- The two existing accepted local hotpatch **source** images (production source
  and VM source), not their different host-native Docker 29 inventory IDs.
- Immutable nginx and Caddy fixture references declared in the script. Those
  images were preloaded explicitly; the script itself never pulls images.
- A uniquely named disposable bridge, PHP-FPM fixture and nginx container.
  It mounts only test configuration read-only, never deployment data or secrets.
- By default, the official Caddy binary extracted from its fixture image, run unprivileged
  on a random **loopback-only TLS listener** with a synthetic self-signed
  certificate. No host networking, trust-store installation, Caddy admin
  endpoint or host Caddy configuration is used.
- A test-only PHP endpoint loading the accepted image's actual Composer
  libraries and Invoice Ninja proxy middleware. FPM runs with `-n` and the
  fixture pool, not the normal application entrypoint, queue or scheduler.
  There is no application bootstrap, real user login, database or production
  token. **Never deploy `tests/fixtures/proxy/` as an application endpoint.**

Results on both accepted source images:

| Request path / attack | Result |
|---|---|
| Internal peer spoofs client IP, host, HTTPS, port, prefix and alternate forwarded headers | Rejected: exact peer IP preserved; `http://nginx:80` semantics preserved; forwarded headers removed |
| Host Caddy TLS request spoofs client IP, host, HTTP downgrade, port and alternate forwarded headers | Rejected: actual client IP, billing hostname, HTTPS, port 443 and generated HTTPS URL preserved |
| Both paths carry synthetic Authorization, API-token and cookie headers | Headers and cookie preserved, as was `/api/v1/clients` routing |
| Missing, malformed or multiple default routes | Startup rejection covered by secret-free regression tests |

Test Caddy was **2.11.7**. nginx used the immutable fixture in the script; this
does **not** change the deployment's nginx reference. The real PHP middleware
was exercised for both accepted source images. All fixture containers, their
anonymous image volumes, networks, native Caddy processes and temporary files
were cleaned up by the harness. Reviewed fixture images remain in local Docker.
Focused regression results were **11 security/startup tests and 18 image tests
passing**, with no skips. Full discovery ran 222 test methods and retained the
same 53 pre-existing failure/subtest entries, with zero errors and skips; the
whole suite is still not green. Ansible lint, YAML lint, both playbook syntax
checks and Python syntax compilation also passed.

To repeat, preload the script's nginx/Caddy fixtures and choose one accepted
local source ID documented in `tests/test_invoiceninja_vm_hotpatch.py`:

```bash
/usr/bin/python3 tests/proxy_smoke.py --app-image "$ACCEPTED_LOCAL_PHP_IMAGE"
/usr/bin/python3 -m unittest discover -s tests -p test_deployment_security.py -v
/usr/bin/python3 -m unittest discover -s tests -p test_invoiceninja_vm_hotpatch.py -v
```

The harness rejects remote Docker contexts/hosts, non-Linux execution, mutable
application tags and assertion-disabling Python optimization. Requires system
Python with PyYAML/Jinja2, Docker, OpenSSL and a preloaded accepted image.
`--expect-vulnerable` was used to reproduce the original configuration **before
the fix**; it is not expected to pass against the hardened checkout.

CI automatically runs the eleven secret-free configuration/startup/safety contracts and
18 existing image contracts. The full local proxy harness is not automatically
run on GitHub: the accepted host-local images are not available to that runner.
This limitation must not be represented as continuous runtime integration
coverage.

## VM rollout and verification — completed

The authorized target was the existing `local_vm` inventory host
`deploy@in.mplytics.eu` (`openclaw`), project `/opt/fk-cesis`, **Ubuntu 24.04.5
LTS**, Docker **29.8.1** and host Caddy **2.11.4**. Production was not contacted.

Before changing the deployed project:

- A sanitized Caddy adaptation confirmed the billing upstream was
  `127.0.0.1:8089`, with no trusted-proxy configuration or forwarded-header
  overrides; the only request-header customization was `X-Request-Id`.
- nginx's actual default-route gateway was `172.22.0.1`. Its cached tag and
  running image matched, preventing a silent image refresh during recreation.
- The isolated harness passed **on the VM**, using its accepted native Invoice
  Ninja ID, its actual nginx image ID and installed Caddy binary, without image
  pulls, real application mounts or access to deployment secrets.
- A temporary, exact-host-guarded Ansible playbook passed lint, YAML and syntax
  checks. Its `--check --diff` preview reported `ok=16 changed=5 failed=0`.
  Compose diffs/output were suppressed with `diff: false` and `no_log`; the
  safe nginx source diffs remained visible. No Vault decryption was needed.

The harness now supports this no-download VM workflow:

```bash
/usr/bin/python3 tests/proxy_smoke.py --inventory local_vm \
  --app-image "$ACCEPTED_VM_IMAGE" --nginx-image "$VM_NGINX_IMAGE" \
  --caddy-binary /usr/bin/caddy
```

The nginx override must be an immutable ID/digest, never a mutable tag; the
native Caddy override must be an existing executable. New regression coverage
rejects unsafe inputs before container operations. The native binary starts a
separate loopback-only fixture; it does not restart the host Caddy service.

### Backup and targeted apply

The protected checkpoint is:

`/opt/backups/fk-cesis/pre-proxy-hardening-20261028T142309Z`

The directory is root-owned mode 0700, and artifact/operational files are 0600.
Backups and data never left the VM. It contains the original Compose/nginx
files, a private `.env` copy, before/after fingerprints, private startup logs,
database and quiesced storage/public archives, checksums and reviewed one-off
operational scripts. Never commit or upload its contents.

An initial transactional database dump was restored into disposable MariaDB
**11.8.6**, using the exact existing DB image, no network/ports and tmpfs data.
Then the scheduler and both queue workers were stopped gracefully, followed
by Invoice Ninja, for a fresh coherent database/storage/public snapshot. No
pending application source migrations were found before recreation.

The temporary operational playbook edited only debug/logging/proxy environment
fields, nginx's startup command and the two reviewed nginx files. Its actual
apply also reported `ok=16 changed=5 failed=0`. The expanded before/after Compose
models were compared privately, allowing only those specific field changes.
Neither the full-stack role nor MMS startup/migrations were run. Only these
services were recreated:

```bash
docker compose -p fk-cesis -f /opt/fk-cesis/docker-compose.yml \
  --env-file /opt/fk-cesis/.env up -d --no-deps --pull never invoiceninja nginx
```

### Post-apply results

| Check | Observed result |
|---|---|
| Effective Laravel configuration | Cached and environment debug false; trust `127.0.0.1,::1`; PHP 8.4.27; stack/warning logging |
| Real host Caddy TLS path with spoofed forwarded headers | Client login 200; nginx observed actual loopback probe client `127.0.0.1`, instead of the pre-fix bridge gateway `172.22.0.1` |
| Session cookies | Session cookie remained Secure and HttpOnly; XSRF cookie remained Secure |
| Existing MMS credentials, read-only `/clients?per_page=1` | Authenticated 200 before and after; body discarded; no credentials or PII printed |
| MMS health | 200; MMS containers were not restarted |
| All active HTTPS routes through host Caddy | Billing login, Docuseal root and MMS health each returned 200 with normal certificate validation |
| Missing/invalid API token | Normal Invoice Ninja **403 `Invalid token`**, message-only JSON; no trace, exception/file/line fields or spoofed hostname |
| Actual application logger as UID 33 | Synthetic warning successfully written to its normal log while effective debug was false |
| Synthetic PDF, isolated existing image | 16,687 bytes with `%PDF-` magic; no real invoice, application bootstrap or network |
| Invoice Ninja processes | FPM, both queue workers and scheduler RUNNING after restart; no forced jobs |
| Startup audit | Recreated at 14:24:25/26 UTC; startup reported `Nothing to migrate`; zero PHP-fatal/uncaught/SQLSTATE lines in the protected startup capture |
| Fresh quiesced DB backup recovery | Restored 77 tables into a second isolated tmpfs MariaDB; `mariadb-check` passed |
| Storage/public backup recovery | Extracted and hash-checked 24 storage and 1,379 public regular-file payloads in private temporary directories; two public links retained as archive metadata and deliberately not followed |
| Schema and migration ledger | Normalized schema and migration-table hashes unchanged |
| Images and unrelated containers | Both affected image IDs unchanged; all 13 unrelated running containers retained IDs, image IDs and start times |
| Credentials and Caddy ownership | `.env` bytes unchanged; host Caddy file hashes, service PID and start timestamp unchanged |

Final audit confirmed backup permissions and unchanged unrelated containers.
All proxy/restore fixture containers and networks were gone; the temporary VM
validation workspace was removed. The protected backup and rollback evidence
were retained. No production connection or restart was made during that VM
rollout; the later read-only production inspection is recorded separately.

The initial error-response probe incorrectly expected HTTP 401. Investigation
showed this accepted application returns 403 `Invalid token` for both missing
and invalid tokens, regardless of `X-Requested-With`. The expectation was
corrected without changing the application; completed recovery/PDF/logging
checks were not repeated. There is no outstanding error-response failure.

The ordinary scheduled backup issue documented in the earlier hotpatch runbook
was not repaired or certified by this rollout; this independently restored
one-off checkpoint was the safety backup. These recovery checks cover the
affected Invoice Ninja data, not a new certification of every service's backup.
The user subsequently assigned routine daily backup handling to the separate
`server-backups` project and deferred that work here. The legacy role/cron was
not removed or changed; one-off deployment checkpoints remain separate.

## Remaining acceptance gates and threat boundary

1. **VM and production rollout gates passed for the observed topology.** Revalidate after topology changes or before subsequent maintenance. This approach assumes host-native
   Caddy, conventional rootful Docker IPv4 bridge networking and the existing
   `127.0.0.1:8089:80` publication. Rootless Docker, userland proxy differences,
   host networking, IPv6-only or multi-default-route configurations need their
   own ingress proof. Do not broaden the trust list to make a failed test pass.
2. **Production Caddy was inspected read-only on 2026-10-29.** Active config matched
   its adapted on-disk source, with no proxy-trust or forwarded-header override
   on billing. Recheck for drift before approved changes. Both inventories
   currently leave Caddy host-owned. Standard Caddy ignores untrusted incoming
   forwarded IP/host/proto headers; any custom header overrides, trusted proxies,
   CDN or PROXY-protocol layer need review. This test covers direct-to-Caddy
   ingress, not arbitrary CDN chains. Host-local processes are inside this
   trust boundary because they can reach the loopback publication.
3. **Interactive/business-flow acceptance remains partial.** VM checks cover
   the real login page, session cookie attributes, authenticated read-only MMS
   API, application logging, sanitized API errors and synthetic PDF generation.
   Production proxy/logging checks passed, but the existing configured MMS API
   credential still returns 403 `Invalid token`, unchanged from its baseline.
   That integration is not green and needs separately authorized repair.
   Authenticated browser login and real invoice/client-portal/mail/payment
   workflows were not exercised; no invoices, payments or email sends were
   deliberately triggered. Those are not implied by the fixture results.
4. **Shared-network compromise is not solved here.** Services still share the
   existing network, including PHP-FPM reachability. Direct FastCGI access,
   raw-packet/ARP attacks from a compromised container and broader lateral
   movement need separate network/capability isolation. This fix addresses
   normal HTTP header spoofing through nginx, not a hostile Docker host or a
   complete container-compromise threat model.

## Approved rollout procedure and paired rollback

The scoped VM and separately approved production rollouts are complete. The
linked production report records its own preflight, protected recovery gate,
scoped apply and checks. Further production changes outside that approval still
require their own authorization. The VM-only operational helper must not be
repurposed blindly for production.

Deploy these as one reviewed unit: Compose command/proxy environment, nginx
startup script, Laravel nginx config and the role's script deployment task.
Keep all existing images preloaded (`--pull never`). Applying the ordinary
whole-stack role can start unrelated services and run MMS migrations, so the
operator must review and scope the actual apply rather than using it merely
to inspect this change. Only nginx and Invoice Ninja need a configuration
restart/recreation for this fix, with a Laravel configuration-cache check.

For rollback, restore the **paired previous** Compose command and nginx config
and recreate only approved affected services; removing the script while leaving
its nginx include or Compose command would break startup. Keep debug false and
all image pins, volumes and credentials unchanged. Restoring wildcard trust
reintroduces the demonstrated spoofing flaw: use only as a time-bounded
incident rollback, and restrict ingress until the hardened configuration is
revalidated. Never use `down -v` or modify database schema for this proxy change.

The VM checkpoint retains a prepared rollback helper (not executed during the
successful rollout). After a separate rollback decision, review it and use:

```bash
sudo -n env FK_PROXY_BACKUP=/opt/backups/fk-cesis/pre-proxy-hardening-20261028T142309Z \
  python3 /opt/backups/fk-cesis/pre-proxy-hardening-20261028T142309Z/operations/fk-proxy-vm-activate.py rollback
```

It guards the VM identity, unchanged `.env` and image identities, and refuses
to overwrite newer config changes. A rollback reintroduces wildcard trust,
so it is incident recovery, not a security-approved steady state. The private
backup must remain available; no backup was pruned or removed.
