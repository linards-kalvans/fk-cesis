# Invoice Ninja PHP 8.4.27 security hotpatch (VM and production patched)

Runbook for building and verifying derived Invoice Ninja images that upgrade
**only** the PHP patch level to **8.4.27**, which fixes **CVE-2026-109618** and
**CVE-2026-109619**, plus minimal Compose/inventory integration, disposable local
application smoke, and the completed VM and production cutovers on 2026-10-22.

**Current status: VM and production patched.** The user-authorized production
rollout is complete. Both inventories select their own verified Docker 29 native
image IDs through `football_club_stack_invoiceninja_image`; the role default
remains the original upstream fallback. Accepted classic Docker config IDs are
source/build provenance, not inventory pins. Each live Compose change affected
only the Invoice Ninja image line; `.env` bytes remained unchanged. Images were
not pushed. Production API authentication remains blocked by a proven pre-existing
MMS credential mismatch, not a PHP regression; see the production evidence below.
Earlier production-untouched statements describe historical VM-only checkpoints.

## Superseded candidates

Earlier local candidates (`…:8.4.27-prod` id `sha256:0e618b51…`, `…:8.4.27-vm` id
`sha256:e87c0f01…`) replaced only four files (`php`, `php-fpm`, `opcache.so`,
`sodium.so`) and are **NOT CVE-complete**: the upstream fix touches `ext/exif`,
`ext/gd`, `ext/intl` and `ext/soap`, so the retained `exif.so`/`gd.so`/`intl.so`/
`soap.so` still contained the vulnerable code. Those images may remain as
historical local images but must not be treated as accepted. The current
candidates below rebuild every bundled shared extension and supersede them.

## What is produced

- Source of truth: `docker/invoiceninja-php-hotpatch/`
  - `Dockerfile` — two-stage build (builder compiles PHP 8.4.27 from verified
    upstream source; final stage is the pinned base with only the PHP runtime
    artifacts replaced).
  - `common.sh` — approved base allowlist, fail-closed daemon preflight,
    deterministic filesystem-manifest comparison, symbol-resolution snippet.
  - `build-php.sh` — safe, local-only build driver.
  - `verify.sh` — base/candidate equivalence and runtime verification driver.
  - `smoke-local.sh` — disposable local application smoke (internal network,
    synthetic credentials, no workers, no published ports, own-artifact cleanup).

## Approved bases

Only these digest-pinned images are accepted. Mutable tags (`:latest`, `:8.4`,
…) and any other digest are rejected before Docker is invoked.

| Host | Index (OCI index, provenance) | Build reference (linux/amd64 child) | Base PHP | IN image label |
|---|---|---|---|---|
| Production | `invoiceninja/invoiceninja-debian@sha256:293ada121c633096e387fc7103b221a2c2a2aee95b8d9ef34991bf57de8f505b` | `invoiceninja/invoiceninja-debian@sha256:f938079be2b24df0fe5f1478c281df9011c658f3ad46fc02173bc578bb923fe0` | 8.4.22 | 5.13.26-d |
| Local VM | `invoiceninja/invoiceninja-debian@sha256:673fac38a57de324e120d57dd0c05d35d9a914bac588e9a9438a19a3c74feebc` | `invoiceninja/invoiceninja-debian@sha256:587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd` | 8.4.20 | 5.13.21-d |

Both bases are Debian 13 (trixie), amd64, NTS, with `/usr/local/bin/php`,
`/usr/local/sbin/php-fpm` and extension directory
`/usr/local/lib/php/extensions/no-debug-non-zts-20240924`. The upstream image is
`php:8.4-fpm` plus `install-php-extensions`; its application tree lives in
`/var/www/html` and its pre-built public directory in `/tmp/public`.

## Pinned source

- `https://www.php.net/distributions/php-8.4.27.tar.xz`
- SHA256 `dcf93923b0e38e0d5252b25b796520b5a47761a08b3488b6d0b5d1115764d3f0`
  (confirmed via the php.net releases JSON and the docker-library PHP
  `8.4/trixie/fpm` recipe). The build fails if the downloaded tarball does not
  match this hash.

The build uses the exact global configure options captured from both bases'
`php-config --configure-options`, including `--enable-option-checking=fatal`,
`--with-sodium=shared`, `--with-pdo-sqlite=/usr`, `--with-sqlite3=/usr`,
`--disable-cgi`, `--enable-fpm` and `--with-pear`, plus the per-extension
options needed to reproduce the base's bundled shared modules. PHP 8.5 and
`php:latest` are never used.

## Bundled shared modules: all rebuilt

The upstream fix for CVE-2026-109618 / CVE-2026-109619
(`php-src 31c0ea7d7ff1d1fccb6492e52dab544011628065`, "Avoid state corruption via
bailout") modifies `ext/exif/exif.c`, `ext/gd/libgd/*.c`,
`ext/intl/converter/converter.c` (+ grapheme + normalizer), `ext/soap/*.c` and
the Zend engine. Every bundled shared module present in the baseline is
therefore rebuilt from the same 8.4.27 source, with options matched to the base:

| Module | Baseline | Action | Options used |
|---|---|---|---|
| `bcmath` | shared | **rebuilt** | `--enable-bcmath=shared` |
| `exif` | shared | **rebuilt** | `--enable-exif=shared` |
| `gd` | shared | **rebuilt** | `--enable-gd=shared --with-webp --with-jpeg --with-xpm --with-freetype --with-avif` |
| `intl` | shared | **rebuilt** | `--enable-intl=shared` (distro ICU 76.1) |
| `opcache` | shared | **rebuilt** | `--enable-opcache=shared` |
| `pcntl` | shared | **rebuilt** | `--enable-pcntl=shared` |
| `pdo_mysql` | shared | **rebuilt** | `--with-pdo-mysql=shared,mysqlnd` |
| `soap` | shared | **rebuilt** | `--enable-soap=shared` |
| `sodium` | shared | **rebuilt** | `--with-sodium=shared` |
| `zip` | shared | **rebuilt** | `--with-zip=shared` (libzip 1.11.3 + libbz2) |
| `imagick` | shared | retained (3.8.1) | third-party, load/ABI verified |
| `saxon` (`saxonc`) | shared | retained (12.5) | third-party, load/ABI verified |

Static (compiled-in) modules are unchanged: Core, ctype, curl, date, dom,
fileinfo, filter, hash, iconv, json, libxml, mbstring, mysqlnd, openssl, pcre,
PDO, pdo_sqlite, Phar, posix, random, readline, Reflection, session, SimpleXML,
SPL, sqlite3, standard, tokenizer, xml, xmlreader, xmlwriter, zlib.

## Design: what is retained, what is replaced

The builder stage starts **from the same pinned base**, so the retained
third-party modules are present and untouched when the source-built modules are
staged for the final image. The final stage is the pinned base plus exactly
twelve replaced files:

```
/usr/local/bin/php
/usr/local/sbin/php-fpm
/usr/local/lib/php/extensions/no-debug-non-zts-20240924/{bcmath,exif,gd,intl,opcache,pcntl,pdo_mysql,soap,sodium,zip}.so
```

`imagick.so` and `saxon.so` must be byte-for-byte unchanged. Everything else is
inherited byte-for-byte, including the Invoice Ninja application tree
(`/var/www/html`), `/tmp/public`, the entrypoint (`/usr/local/bin/init.sh`),
`supervisord` configuration (`/etc/supervisor`), the PHP ini and FPM
configuration (`/usr/local/etc`), the `PHPIZE_DEPS`/`PHP_CFLAGS` metadata and
the system/runtime libraries. The build asserts that the shared-extension set is
unchanged, that only the bundled modules differ from the inherited ones, that
every bundled and retained module loads, and that `make install` did not rewrite
any pre-existing ini/FPM config.

`PHP_VERSION`, `PHP_URL`, `PHP_ASC_URL` and `PHP_SHA256` are re-declared in the
final image so the inherited metadata matches the rebuilt runtime. (`ARG`
defaults alone would be shadowed by the base image's own `ENV`, which is why the
builder uses distinct `HOTPATCH_PHP_*` names.)

The Dockerfile itself asserts the approved `BASE_IMAGE` digest, the expected
base PHP release (8.4.22 or 8.4.20), `x86_64` and a non-thread-safe build. A
Dockerfile cannot perform the daemon preflight, so refusing a remote
`DOCKER_HOST`/context is done only by the host drivers.

### Scope note: build tooling and headers

`/usr/local/bin/phpize`, `/usr/local/bin/php-config`, `/usr/local/bin/pecl`,
`/usr/local/bin/pear` and `/usr/local/include/php` are **not** copied into the
final image; they remain at the base's 8.4.x. They are outside the Invoice Ninja
runtime contract (nothing at runtime invokes them), so this is a deliberate scope
boundary rather than a broad copy of the build tree. If a future change needs
extension building inside the running image, that requires a separate approved
decision.

## Build

Requires a local Docker daemon on the unix socket. The scripts refuse a remote
`DOCKER_HOST`/context, never read `.env` or secrets, never use host networking,
never publish ports, never mount volumes and never push. Builds use
`--platform linux/amd64`; compile jobs are bounded (`--jobs 2` default, max 4).

```bash
# Production base (default)
bash docker/invoiceninja-php-hotpatch/build-php.sh

# Local VM base
bash docker/invoiceninja-php-hotpatch/build-php.sh \
  --base invoiceninja/invoiceninja-debian@sha256:587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd

# Inspect the command without running it
bash docker/invoiceninja-php-hotpatch/build-php.sh --dry-run
```

Default local tags: `fk-cesis-invoiceninja-php-hotpatch:8.4.27-prod` and
`…:8.4.27-vm`. Network is used only to fetch public build dependencies and the
SHA256-pinned PHP tarball.

## Verify

```bash
bash docker/invoiceninja-php-hotpatch/verify.sh   # production default
bash docker/invoiceninja-php-hotpatch/verify.sh \
  --base invoiceninja/invoiceninja-debian@sha256:587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd
```

The candidate must already exist locally; it is never pulled. All container
invocations use `--platform linux/amd64`, `--network none` and an overridden
entrypoint (so `init.sh`, supervisord, migrations and any outbound mail/payment
path cannot run). `LD_BIND_NOW=1` is applied only to the PHP and PHP-FPM runtime
checks; the filesystem-manifest checks (`/bin/sh`) and the symbol-resolution
checks (`ldd -r`/`nm`) run separately without it. `verify.sh` checks:

1. The candidate's `fk-cesis.php-hotpatch.base` label equals the selected base;
   `Entrypoint`, `Cmd`, `WorkingDir`, `User` identical; `Env` identical apart
   from the four PHP version-metadata variables, each asserted exactly
   (`PHP_VERSION`, `PHP_URL`, `PHP_ASC_URL`, `PHP_SHA256`).
2. The enumerated trees `/var/www/html`, `/tmp`, `/tmp/public`, `/usr/local/etc`
   and `/etc/supervisor` are byte-for-byte identical (type + uid + gid + mode +
   symlink target + content).
3. The PHP runtime trees change **exactly** the twelve allowed files; metadata
   (type/uid/gid/mode) is identical for the changed paths too.
4. Candidate reports exactly `PHP 8.4.27` via `php -r`, and via exact
   version-token matches `^PHP 8\.4\.27 \(cli\)` / `^PHP 8\.4\.27 \(fpm-fcgi\)`
   for `php -v` / `php-fpm -v` (not a substring or prefix match); it is amd64
   NTS API20240924 and not 8.5.
5. Static (`php -n -m`) and full (`php -m`) module sets are identical to the
   base.
6. Every bundled module loads; `imagick` is exactly 3.8.1 and `saxonc` exactly
   12.5; every extension version matches the base or tracks the 8.4.27 release
   (e.g. `mysqlnd 8.4.27`); gd/intl/zip feature fingerprints match the base.
7. `php-fpm -t` succeeds.
8. `ldd -r` reports no missing libraries and every undefined symbol of every
   shared module is provided by the candidate php executable's full library
   closure (version-stripped symbol comparison via `nm -D --defined-only`).

### What the checks measure (and do not)

Unchanged system libraries are unchanged by construction: the final stage is the
pinned base plus `COPY` of only the PHP runtime artifacts, so no file outside
`/usr/local/bin/php`, `/usr/local/sbin/php-fpm` and the extension directory is
written. `verify.sh` does not perform a full rootfs audit and does not claim one.
It measures exactly: the enumerated trees above, the PHP artifact change set and
its metadata, the image config/Env/labels, the static and full module sets, the
extension versions and gd/intl/zip feature fingerprints, php-fpm config parsing,
and eager symbol resolution for php, php-fpm and every shared module.

## Verified result (local, 2026-10-22)

Both candidates built and passed the full verification on the local daemon:

| Base | Candidate image id | Base PHP | Candidate PHP |
|---|---|---|---|
| Production child | `sha256:14c1af817177f9c81bbeef6a5b3964ed478b5462776b9ed909c6115f1b72b2b6` | 8.4.22 | 8.4.27 |
| Local VM child (classic Docker config digest) | `sha256:68921270adf885a6fcedee6fde24851be517dd6d6b5579df731b688516c7d248` | 8.4.20 | 8.4.27 |

These supersede the earlier four-file candidates. Both bases were confirmed to
have identical PHP module sets (34 static, 47 full) and identical
extension-directory listings.

On the Docker 29 VM, the local VM child is stored and reported as OCI
manifest/image ID
`sha256:9248d42e08d5cfbbdb7da7ffb0b8ac9e925df511bd5a625770566c329c6b928f`.
This is the same image: the manifest's config descriptor and the 22,261-byte
config blob both hash to the classic config ID above. The VM inventory therefore
pins the VM-native ID; the classic ID stays as source/build and smoke provenance.

## Deployment image selection

Image selection is one variable, `football_club_stack_invoiceninja_image`:

| Render | Selected image | Intent |
|---|---|---|
| Role default | `invoiceninja/invoiceninja-debian:latest` | unchanged upstream fallback for inventories without an override |
| Production inventory | `sha256:b8e368e6fa68c2a715d0100455f06e17827d4652398c63e2fcaed092f2b0632e` | verified production-native OCI image ID for the accepted production hotpatch; application 5.13.26-d, PHP 8.4.27; no registry access needed |
| Local VM inventory | `sha256:9248d42e08d5cfbbdb7da7ffb0b8ac9e925df511bd5a625770566c329c6b928f` | verified VM-native OCI image ID for the accepted local VM hotpatch image (`fk-cesis-invoiceninja-php-hotpatch:8.4.27-vm`); no registry access needed |

The Compose template uses the variable for the `invoiceninja` service.
`docker compose config` accepts the full `sha256:` image ID. The VM image is the
existing candidate: application 5.13.21-d, PHP 8.4.27, every bundled shared
module rebuilt (including the critical `exif`, `gd`, `intl` and `soap` fixes),
with only `imagick` and `saxonc` retained. Do not rebuild it for rollout.

Focus contract tests:

```bash
pytest tests/test_invoiceninja_vm_hotpatch.py tests/test_invoiceninja_php_hotpatch.py -q
```

## Disposable local application smoke

`smoke-local.sh` never pulls, pushes, publishes a port, mounts live data, reads
the vault or runs `init.sh`/supervisord. It creates its own internal Docker
network (no external egress), disposable named volumes, MariaDB with synthetic
credentials, and an application container with an overridden entrypoint. Cache,
session and queue are forced to `array`/`array`/`sync`, so Redis and workers are
not used.

```bash
bash docker/invoiceninja-php-hotpatch/smoke-local.sh
```

What it actually checks:

- PHP 8.4.27 and the rebuilt `exif`, `gd`, `intl`, `soap` modules, plus retained
  `imagick`/`saxonc`, with `php-fpm -t`.
- Snappdf PDF generation from synthetic benign HTML (not a real invoice), using
  the Chrome already inside the candidate and `--network none`.
- Supervisor configuration inspection only: the normal entrypoint is not run,
  and the smoke asserts no `supervisord`, `queue:work` or `schedule:work`
  process is present.
- Migrations and seeding against disposable MariaDB, a synthetic account, then a
  loopback `GET /client/login` asserting HTTP 200 and a rendered password field.
  Authenticated login is **not** tested.
- No published ports, internal network asserted, and cleanup removes only the
  containers/network/volumes created by this run, including the MariaDB
  anonymous volume (`docker rm -fv`). No prune.
- Heredoc-fed PHP checks run with `docker run -i`; a focused test asserts every
  heredoc-fed Docker run is interactive, so the capability gate cannot be
  silently skipped.

Local result (2026-10-22): passed; PDF 15,591 bytes with `%PDF-` magic; login
view `200`; MariaDB 12.3.2 from local cache; no Redis. Real invoices, mail,
payments, workers and the scheduler were never exercised.

## VM rollout (controller-completed, 2026-10-22)

**The automated nightly backup is not usable and was not the rollout backup.**
Controller inspection of the VM found that
`20261022_020001` and the preceding backup directories contain a zero-byte
`ninja.sql` and no storage backups. `backup.sh` has no `mysqldump`; only
`mariadb-dump` exists. Do not repair the nightly job as part of this rollout.
It remains broken/unfixed.

The following results are controller-confirmed evidence, not checks rerun by this
documentation update:

- The full verifier passed **on the VM** for candidate `9248…` against the
  original VM base `673fac…`, without pulls. A small temporary verification copy
  mapped runtime base lookup to the existing VM index while still checking the
  canonical child provenance label `587fb…`; temporary scripts were deleted.
  Checks used no network or mounts and overridden entrypoints: exact CLI/FPM
  8.4.27, NTS API20240924, exactly 12 changed files, identical application/config/
  public/tmp trees and metadata, 34 static/47 full modules, all ten bundled shared
  modules rebuilt, retained imagick 3.8.1/saxonc 12.5, feature parity, and
  `LD_BIND_NOW`/`ldd` checks passed.
- The initial backup below was restored into disposable, same-VM MariaDB 11.8.6
  using existing image
  `sha256:78a5047d3ba33975f183f183c2464cc7f1eab13ec8667e57cc9a5821d6da7577`.
  Import restored 77 tables and `mariadb-check` passed. Isolation was
  `--network none`, no ports, mysql/tmp on tmpfs, 768 MiB memory and one CPU;
  container and volumes were removed, leaving no disposable restore data.
  No destructive live restore occurred and no backup data left the VM.
- Before the fresh backup, the explicit **at least 512 MiB free** disk gate
  passed with **2,394,776 KiB available**. The controller gracefully stopped the
  scheduler, then both queue workers with `supervisorctl stop`, waited for stopped
  state, then stopped only Invoice Ninja. The fresh quiesced backup is
  `/opt/backups/fk-cesis/pre-php8427-quiesced-20261022T103953Z`: database, storage,
  public, Compose and private `.env`, directory mode 0700 and files 0600.
  Gzip/tar integrity, completion marker, 77 tables and SHA256 checks passed.
  Compressed artifact sizes were 87,931 bytes (database), 443,197 bytes
  (storage) and 64,859,217 bytes (public assets).
  Unrelated-container baselines and migration/schema hashes were stored privately
  there. No backups were deleted and no prune ran.
- A reviewed temporary operational playbook,
  `/tmp/opencode/fk-cesis-php8427-vm-image.yml`, guarded the exact VM host and
  excluded production groups, asserted candidate presence, and used `lineinfile`
  for **only the image line**, with quiet Compose validation and a post-assertion
  of `9248…`. Syntax check passed; `--check --diff` reported
  `ok=4 changed=1 failed=0`; apply reported `ok=6 changed=1 failed=0`.
  This was not new permanent infrastructure or a full-stack Ansible run.
  Live byte comparison proved exactly one Compose image line changed and `.env`
  remained byte-for-byte unchanged.

The controller recreated only Invoice Ninja, with no pull or dependency restart:

```bash
docker compose -p fk-cesis -f /opt/fk-cesis/docker-compose.yml \
  --env-file /opt/fk-cesis/.env up -d --no-deps --pull never invoiceninja
```

The replacement started at `2026-10-22T10:40:57.976058774Z`, is healthy, and
runs image `9248…` with PHP CLI/FPM **8.4.27** and unchanged application
**5.13.21-d**. The normal entrypoint refreshed cache/design/public assets,
reported **“Nothing to migrate”** and completed production setup before starting
supervisor; that startup message does not indicate a production-host rollout.
Migration-table and schema hashes remained unchanged. Raw startup logs are private
at `startup.private.log` in the quiesced backup (0600); error-level/fatal/uncaught
line count was zero. FPM, both queue workers and the scheduler are RUNNING;
workers/scheduler resumed once, with no duplicate old workers or forced jobs.
All **14 unrelated running containers** retained their IDs, images and start times.

Post-cutover checks passed: VM `http://127.0.0.1:8089/client/login` and public
`https://billing.mplytics.eu/client/login` returned **200**. Synthetic PDF output
was **15,645 bytes** with valid `%PDF` magic in a separate candidate container
with no network, mounts, application bootstrap or real invoice. From the existing
`mms-web` container, an authenticated read-only GET to its configured
`INVOICE_NINJA_API_URL` plus `/clients?per_page=1` returned **200** using existing
credentials internally; the body was discarded and no PII or credentials printed.
MMS `/healthz` also returned **200**. These checks made no invoice-creation,
mail or payment requests; authenticated UI login was not tested.

### Earlier controller checkpoint (superseded by completed cutover above)

At this earlier stopped checkpoint, only VM inspection, import and preparation
had run: no live Compose/environment change or service replacement had yet
occurred. The following records preserve historical evidence, not current status.

- VM baseline remained PHP CLI/FPM **8.4.20**, with the original image ID above;
  container start time remained `2026-09-25T12:51:59.681431005Z`.
- Created root-only one-off backup directory
  `/opt/backups/fk-cesis/pre-php8427-20261022T100545Z` (mode 0700, root:root).
  Database dump: **87,931 bytes compressed**, **77 CREATE TABLE statements**,
  dump-completion marker present. Storage/public archives: **442,744** and
  **64,859,217 bytes**. Gzip/tar integrity and SHA256 checks passed for the
  database, both archives, Compose and the private environment copy. Artifact
  files are mode 0600. No contents or credentials left the VM. These are
  structural/integrity checks only at this checkpoint; the isolated restore test
  documented above passed later. This initial snapshot was taken while the
  original application remained running.
- Streamed the existing candidate with `docker image save | gzip | ssh ...
  docker image load`; no registry, rebuild or remote archive file.
- **Image-identity gate resolved without archives or layer diffs.** The classic
  Docker config digest
  `sha256:68921270adf885a6fcedee6fde24851be517dd6d6b5579df731b688516c7d248`
  and the VM Docker 29 OCI manifest/image ID
  `sha256:9248d42e08d5cfbbdb7da7ffb0b8ac9e925df511bd5a625770566c329c6b928f`
  are the same image. Verification used the VM's containerd content store
  (`/run/containerd/containerd.sock`, namespace `moby`):
  - `ctr -n moby content get sha256:9248…` returns manifest bytes whose SHA256
    is exactly `9248…`.
  - That manifest's config descriptor digest is `6892…`; the 22,261-byte config
    blob's SHA256 is exactly `6892…`, the accepted source config ID.
  - Parsed config `rootfs.diff_ids` match all **26** local accepted source
    `RootFS.Layers` exactly.
  - All **26** manifest layer descriptors are
    `application/vnd.oci.image.layer.v1.tar` and their digests equal the
    ordered `diff_ids`. The controller rehashed the actual config and all 26
    layer blobs via `ctr content get | sha256sum` with rc 0.
  - OS/architecture is `linux/amd64`; inspected `Config`/`RootFS` are
    identical across engines. Raw config bytes and normalized `inspect`
    defaults can differ; the digest chain above is the stronger evidence.
  - No text-ID equality is required between engines. Background:
    <https://docs.docker.com/engine/storage/containerd/> and the Docker API
    `ImageManifestSummary` field semantics
    (<https://github.com/docker/docs/blob/main/_vendor/github.com/moby/moby/api/docs/v1.56.yaml>).
  - The earlier read-only exported-config identity diagnostic exceeded its
    120-second timeout without producing evidence; the content-store check
    supersedes it.
- The repository VM pin now records the verified VM-native ID `9248…`. The
  accepted source/config ID `6892…` remains the local build and smoke
   provenance (the smoke default is unchanged). At this historical checkpoint,
   production still rendered the original upstream default.
- VM free disk after import: **2.3 GiB (94% used)**. No new archives were
  created, and no images or volumes were pruned. The verification was bounded
  in resource use.

The earlier cutover stop is superseded: disk gating, fresh quiesced backup,
isolated database restore validation, VM `--check --diff`, apply and the
Invoice-Ninja-only cutover have now completed as recorded above.

## Production rollout (controller-completed, 2026-10-22)

These are supplied controller results, not checks rerun by this documentation edit.
The authorized target `netcup-prod-1.tail45ce0a.ts.net` and actual hostname
`netcup-prod-1` were confirmed before mutation: Docker 29.8.1, initially 226 GiB
free, no configuration drift, PHP CLI/FPM 8.4.22 and application 5.13.26-d.
The original image was `293ada…` (full rollback ID below); application code had
no drift beyond bootstrap cache and the public volume.

- The accepted local production source/config `14c1…` (full ID above) was streamed
  directly with save/load: no gzip/archive file, registry access or rebuild.
  Production's native manifest/image ID is `b8e368…` (full inventory pin above).
  Its manifest bytes hash to that ID; its config descriptor and actual 22,654-byte
  config blob hash to `14c1…`. All 26 ordered uncompressed layer descriptors match
  the source RootFS diffIDs. The actual config and all 26 layer blobs were rehashed
  successfully (rc 0); OS/architecture is linux/amd64.
- The full isolated verifier passed on production without pulls, network, live
  mounts or the normal entrypoint: exact CLI/FPM 8.4.27, NTS, exactly 12 changed
  files, equal application/config/public/tmp trees and metadata, 34 static/47 full
  modules, all ten bundled modules rebuilt, exact retained third-party versions
  and feature parity, plus `LD_BIND_NOW` and `ldd` checks.
- Production's nightly backup was also unusable: `mysqldump` is missing and
  `20261022_020001/ninja.sql` is zero-byte; the offsite destination is a placeholder.
  Backup automation was not repaired or relied upon for this rollout.
- Initial root-only backup:
  `/opt/backups/football-club/pre-php8427-20261022T105907Z`.
  Database gzip was 78,620 bytes with 79 InnoDB tables; storage/public archives
  were 27,086/69,116,688 bytes. Private Compose/environment copies were included;
  directory/files were 0700/0600. Integrity, dump footer, table count and SHA256
  checks passed. An actual restore into isolated same-host MariaDB using existing
  image `sha256:628f228f0fd5913a220438693576b29b6fe4dc1fa0a1298c0e98579fae28635f`
  restored all 79 tables and passed `mariadb-check`: no network/ports, tmpfs data,
  768 MiB/one CPU. Cleanup completed; no disposable data remained or left the host.
- Reviewed temporary playbook `/tmp/opencode/fk-cesis-php8427-production-image.yml`
  guards the exact address and actual hostname, allowing only `b8e368…` forward
  and `293ada…` rollback. It uses task-level become, image-only `lineinfile`, quiet
  Compose validation and a post-assertion. Syntax passed; `--check --diff` reported
  `ok=6 changed=1 failed=0 skipped=2`, exactly one line; apply reported
  `ok=8 changed=1 failed=0`. No full-stack playbook ran.
- The scheduler and two queue workers were gracefully drained to STOPPED before
  stopping only Invoice Ninja. Fresh quiesced root-only backup:
  `/opt/backups/football-club/pre-php8427-quiesced-20261022T110934Z`.
  Database/storage/public and private Compose/environment copies passed gzip/tar,
  footer, 79-table and SHA256 validation, with 0700/0600 permissions. Private
  compressed artifact sizes were 78,619 bytes (database), 27,086 bytes (storage)
  and 69,116,688 bytes (public assets).
  baselines cover seven neighbors and schema/migration hashes. `.env` was unchanged;
  live Compose differed by exactly the image line. The service-only cutover was:

  ```bash
  docker compose -p football-club -f /opt/football-club/docker-compose.yml \
    --env-file /opt/football-club/.env up -d --no-deps --pull never invoiceninja
  ```

The replacement started at `2026-10-22T11:10:27.357854612Z`, healthy on `b8e368…`,
application **5.13.26-d**, PHP CLI/FPM **8.4.27**. FPM, both queue workers and the
scheduler are RUNNING. Conservative interruption was **63 seconds**, from service
stop beginning `11:09:35Z` to first healthy/public login 200 at `11:10:38Z`.
The health poll was bounded to 180 seconds; prepared rollback was not needed.
Startup reported “Nothing to migrate,” completed production setup and started
supervisor. Schema/migration hashes were unchanged; private `startup.private.log`
is root-only 0600 with zero error-level/fatal/uncaught lines. All seven neighbors
retained IDs, images and start times. Public `https://billing.fkcesis.lv/client/login`
and MMS health returned **200**. Isolated synthetic PDF output was **16,619 bytes**,
valid PDF, using `b8e368…` without network, real invoice or application bootstrap.

**Authentication limitation: integration is not all green.** The existing MMS
`INVOICE_NINJA_API_KEY` read-only GET to `http://nginx/api/v1/clients?per_page=1`
returned **403**, public JSON message **“Invalid token.”** Investigation restored
the exact fresh quiesced pre-cutover database into another isolated, network-none,
tmpfs MariaDB. Internal checks using the configured key in root memory via SQL
stdin found **VALIDTOKENMATCHES=0 in both pre-cutover and live databases**.
The MMS container and auth code were unchanged; `TokenAuth.php` performs an exact
CompanyToken lookup, returning 403 when absent. This proves a pre-existing
credential mismatch, not a PHP-patch regression. Read-only review explicitly
approved retaining the patched runtime: PHP 8.4.22 rollback cannot create the
missing token and would reintroduce the CVEs. No credentials/body data were
printed, no token was created or changed, and no secret configuration changed.
Separate credential repair and a later read-only retest are required.

Authenticated UI login and real invoice/mail/payment probes were not tested.
Jobs resumed once for ordinary operation, without forced jobs. No rollback ran.
The production unit did not contact the VM or change its `9248…` pin/runtime,
local smoke defaults or MMS checkout; no commits, pushes, worktrees, blanket
prunes or unrelated service changes occurred. Repository integration is the
production pin, a defaults-comment-only clarification, and 18 shared VM/production
tests alongside 80 hotpatch tests. Final controller checks passed **98 focused
tests**, scoped Ansible/YAML lint, both playbook syntax checks and
`git diff --check`. Production remained healthy with all four supervisor
processes RUNNING and public login 200; disk headroom was **223 GiB free (8% used)**.

## Not done here (deliberately)

- No image publication or live secret change. Both authorized rollouts completed;
  production was untouched only during the earlier VM-only phase.
- Nightly backups remain broken on both hosts; no backup automation was repaired.
- Cross-engine identity mappings are resolved; both inventories record their own
  verified native IDs. No rebuild or registry access was used for rollout.
- No broad infrastructure repair, full-stack deployment or destructive live
  restore. Initial and quiesced backups remain on their respective hosts.

## Limitations

- Nightly backups remain broken on both hosts (`mysqldump` missing; dumps zero-byte).
  Prior VM free disk was **2.3 GiB (94% used)**, not remeasured by the production
  unit. Production final headroom was **223 GiB free (8% used)** and the expanded
  **98-test** controller check passed. Earlier VM controller final checks confirmed
  healthy PHP 8.4.27 with all four supervisor processes RUNNING, the retained
  rollback image, **96 focused tests passed at that checkpoint**, clean scoped
  YAML/Ansible lint, both playbook syntax checks, shell syntax and `git diff --check`.
  The existing 53 broader baseline test failures were not repaired.
- Production MMS API auth has a proven pre-existing credential mismatch requiring
  separate repair; the VM API check passed. Authenticated UI login and live
  invoice/mail/payment workflows were not tested.
  The isolated restore validated the database, not a complete application recovery.
- The derived image is reproducible from a pinned base and pinned source, but
  build dependencies are installed from the live Debian mirrors, so byte-for-byte
  reproducibility of the compile environment is not guaranteed. The gd/intl/zip
  runtime libraries are frozen by the trixie release and verified at runtime.
- `imagick`/`saxonc` are retained from the base and verified by ABI/load checks,
  not rebuilt.

## Rollback

Both hosts now run the hotpatch; neither rollback was performed. The verified
original VM-local image remains available as
`sha256:673fac38a57de324e120d57dd0c05d35d9a914bac588e9a9438a19a3c74feebc`;
before cutover its inspected `Id` matched the container's `.Image` and its
`RepoDigests` included the same digest under
`invoiceninja/invoiceninja-debian`. This is an observed VM-local identity, not
an inferred child/config digest. It ran CLI/FPM 8.4.20 and had started at
`2026-09-25T12:51:59.681431005Z`.

The original production image remains available as
`sha256:293ada121c633096e387fc7103b221a2c2a2aee95b8d9ef34991bf57de8f505b`
(PHP CLI/FPM 8.4.22); root-only backup configuration remains available. Production
rollback uses the same reviewed temporary production playbook with
`-e hotpatch_target=sha256:293ada121c633096e387fc7103b221a2c2a2aee95b8d9ef34991bf57de8f505b`,
then the production service-only Compose command above.

On either host, restore **only** its live Compose `invoiceninja` image line to its
own exact original ID, validate Compose, and use its matching project/path command
with `--no-deps --pull never`. Align that host's persistent inventory pin with the
rollback decision so automation does not reapply a different image. Never use
`:latest`, an unverified registry reference or the other host's image.
**Rollback restores vulnerable PHP (production 8.4.22; VM 8.4.20) and does not fix
production's missing API token.** Leave other services unchanged. There is no
automatic or destructive database restore: migration/schema hashes were unchanged.
Retain each host's initial/quiesced backups, original image and accepted hotpatch.
