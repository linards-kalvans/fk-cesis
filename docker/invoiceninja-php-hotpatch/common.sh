#!/usr/bin/env bash
# Shared constants and safety helpers for the Invoice Ninja PHP 8.4.27 hotpatch.
#
# Sourced by build-php.sh and verify.sh. Deliberately free of credentials: it
# never reads .env, Ansible Vault files or any other secret material, and it
# never contacts a remote Docker daemon.

set -euo pipefail

# --- target patch release -------------------------------------------------
# PHP 8.4.27 fixes CVE-2026-109618 and CVE-2026-109619. The upstream fix
# (php-src 31c0ea7d7ff1d1fccb6492e52dab544011628065, "Avoid state corruption via
# bailout") touches ext/exif, ext/gd, ext/intl, ext/soap and the Zend engine, so
# every bundled shared extension is rebuilt, not only opcache/sodium.
readonly PHP_HOTPATCH_VERSION="8.4.27"
readonly PHP_HOTPATCH_URL="https://www.php.net/distributions/php-8.4.27.tar.xz"
readonly PHP_HOTPATCH_ASC_URL="https://www.php.net/distributions/php-8.4.27.tar.xz.asc"
readonly PHP_HOTPATCH_SHA256="dcf93923b0e38e0d5252b25b796520b5a47761a08b3488b6d0b5d1115764d3f0"

# --- approved immutable bases ---------------------------------------------
# Index digests are recorded for provenance only. The linux/amd64 child
# manifests are the canonical, arch-pinned references used for building and
# comparing, as resolved through the unauthenticated Docker Registry API.
readonly IN_BASE_REPO="invoiceninja/invoiceninja-debian"
readonly PROD_BASE_INDEX="invoiceninja/invoiceninja-debian@sha256:293ada121c633096e387fc7103b221a2c2a2aee95b8d9ef34991bf57de8f505b"
readonly PROD_BASE_AMD64="invoiceninja/invoiceninja-debian@sha256:f938079be2b24df0fe5f1478c281df9011c658f3ad46fc02173bc578bb923fe0"
readonly VM_BASE_INDEX="invoiceninja/invoiceninja-debian@sha256:673fac38a57de324e120d57dd0c05d35d9a914bac588e9a9438a19a3c74feebc"
readonly VM_BASE_AMD64="invoiceninja/invoiceninja-debian@sha256:587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd"

readonly PROD_BASE_PHP_VERSION="8.4.22"
readonly VM_BASE_PHP_VERSION="8.4.20"

readonly PHP_EXT_DIR="/usr/local/lib/php/extensions/no-debug-non-zts-20240924"
readonly CANDIDATE_REPO="fk-cesis-invoiceninja-php-hotpatch"
readonly BUILD_PLATFORM="linux/amd64"
readonly MAX_JOBS=4

# Bundled shared extensions present in both approved bases. All of them are
# rebuilt from the verified 8.4.27 source (per-extension options matched to the
# base: gd with jpeg/webp/freetype/xpm/avif, intl against the distro ICU, zip
# against libzip+libbz2).
readonly BUNDLED_SHARED_MODULES=(bcmath exif gd intl opcache pcntl pdo_mysql soap sodium zip)
# Third-party extensions retained byte-for-byte from the base and verified by
# explicit load/ABI checks only.
readonly RETAINED_THIRD_PARTY_MODULES=(imagick saxon)

# Trees that must stay byte-for-byte identical between base and candidate
# (content + type + uid + gid + mode + symlink target).
# /var/www/html is the Invoice Ninja application; /tmp/public is the pre-built
# public directory copied by the upstream image; /usr/local/etc holds the PHP
# ini and FPM configuration; /etc/supervisor is part of the startup contract.
readonly IDENTICAL_TREES=(/var/www/html /tmp /tmp/public /usr/local/etc /etc/supervisor)

# PHP runtime trees in which only the source-built artifacts may differ.
readonly PHP_TREES=(/usr/local/bin /usr/local/sbin /usr/local/lib/php/extensions)

# The only files the hotpatch is permitted to change: the PHP CLI binary, the
# PHP-FPM binary and every bundled shared module.
readonly ALLOWED_PHP_CHANGES=(
  "/usr/local/bin/php"
  "/usr/local/sbin/php-fpm"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/bcmath.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/exif.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/gd.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/intl.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/opcache.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/pcntl.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/pdo_mysql.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/soap.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/sodium.so"
  "/usr/local/lib/php/extensions/no-debug-non-zts-20240924/zip.so"
)

# --- helpers ---------------------------------------------------------------

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
log()  { printf '%s\n' "$*"; }

# Map an allowed base reference to "<slug> <canonical-amd64-ref> <base-php-version>".
# Rejects mutable tags (:latest, :8.4, ...) and any unapproved digest.
resolve_base() {
  local ref="${1:-}"
  case "$ref" in
    "$PROD_BASE_AMD64"|"$PROD_BASE_INDEX") printf 'prod %s %s\n' "$PROD_BASE_AMD64" "$PROD_BASE_PHP_VERSION" ;;
    "$VM_BASE_AMD64"|"$VM_BASE_INDEX")     printf 'vm %s %s\n'   "$VM_BASE_AMD64"   "$VM_BASE_PHP_VERSION" ;;
    *) fail "refusing base '${ref}': only the two approved digest-pinned Invoice Ninja bases are allowed (prod amd64 ${PROD_BASE_AMD64}, vm amd64 ${VM_BASE_AMD64}); mutable tags and unapproved digests are rejected" ;;
  esac
}

# Refuse to run against anything but the local unix-socket daemon. Fails
# closed: a failed or empty context inspection is an error, never a pass.
# Explicit BuildKit/Buildx overrides are also refused because they can redirect
# the build to a remote builder and bypass this daemon preflight.
preflight_local_docker() {
  if [ -n "${DOCKER_HOST:-}" ] && [ "${DOCKER_HOST}" != "unix:///var/run/docker.sock" ]; then
    fail "DOCKER_HOST='${DOCKER_HOST}' is not the local unix socket; refusing to contact a remote daemon"
  fi
  if [ -n "${BUILDKIT_HOST:-}" ]; then
    fail "BUILDKIT_HOST='${BUILDKIT_HOST}' can redirect the build to a remote builder; refusing"
  fi
  if [ -n "${BUILDX_BUILDER:-}" ]; then
    fail "BUILDX_BUILDER='${BUILDX_BUILDER}' can select a non-local buildx builder; refusing"
  fi
  local endpoint
  if ! endpoint="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null)"; then
    fail "could not inspect the active docker context; refusing to proceed"
  fi
  case "$endpoint" in
    "unix:///var/run/docker.sock") : ;;
    "") fail "active docker context endpoint is empty; refusing to proceed" ;;
    *) fail "active docker context endpoint '${endpoint}' is not the local unix socket; refusing" ;;
  esac
  docker info >/dev/null 2>&1 || fail "docker daemon unreachable on the local unix socket"
}

# Deterministic manifest snippet executed INSIDE a container. It records type,
# uid, gid, mode, path, symlink targets and a content hash so two images can be
# compared without trusting mtimes or inode numbers. The path is always the
# third field of an "H" line and the fifth field of a "D"/"L"/"F" line.
readonly MANIFEST_SNIPPET='
cd "$1" 2>/dev/null || { echo "MISSING_TREE $1" >&2; exit 1; }
find . -xdev -type d -printf "D %u %g %m %p\n" | LC_ALL=C sort
find . -xdev -type l -printf "L %u %g %m %p -> %l\n" | LC_ALL=C sort
find . -xdev -type f -printf "F %u %g %m %p\n" | LC_ALL=C sort
find . -xdev -type f -exec sha256sum {} + | sed "s/^/H /" | LC_ALL=C sort
'

# Print the manifest of a tree inside an image. Never uses host mounts, never
# uses host networking, always pins the platform and never runs the entrypoint.
container_manifest() {
  local image="$1" tree="$2"
  docker run --rm --platform "$BUILD_PLATFORM" --network none --entrypoint /bin/sh "$image" -c "$MANIFEST_SNIPPET" sh "$tree"
}

# Changed paths between two manifest files (one per line, sorted, unique).
manifest_changed_paths() {
  diff "$1" "$2" 2>/dev/null | sed -n 's/^[<>] //p' | awk '{ print ($1 == "H") ? $3 : $5 }' | LC_ALL=C sort -u || true
}

# Metadata-only view of a manifest (type/uid/gid/mode/target, no content hash).
manifest_meta() { grep -v '^H ' "$1" || true; }

# Assert a tree is byte-for-byte identical (content + metadata) between manifests.
assert_no_changes() {
  local base_manifest="$1" candidate_manifest="$2" label="$3"
  local changed
  changed="$(manifest_changed_paths "$base_manifest" "$candidate_manifest")"
  if [ -n "$changed" ]; then
    printf 'ERROR: %s must be byte-for-byte identical but differs:\n%s\n' "$label" "$changed" >&2
    return 1
  fi
  log "OK: ${label} identical (content + uid/gid/mode)"
}

# Assert metadata (type/uid/gid/mode/symlink target) is identical everywhere,
# even for paths whose content is allowed to change.
assert_metadata_unchanged() {
  local base_manifest="$1" candidate_manifest="$2" label="$3"
  local bm cm out
  bm="$(mktemp)"; cm="$(mktemp)"
  manifest_meta "$base_manifest" > "$bm"
  manifest_meta "$candidate_manifest" > "$cm"
  if ! out="$(diff -u "$bm" "$cm")"; then
    rm -f "$bm" "$cm"
    printf 'ERROR: %s metadata (type/uid/gid/mode/target) differs:\n%s\n' "$label" "$out" >&2
    return 1
  fi
  rm -f "$bm" "$cm"
  log "OK: ${label} metadata (type/uid/gid/mode) identical"
}

# Assert the changed-path set equals exactly the allowed artifacts.
assert_only_allowed_changes() {
  local base_manifest="$1" candidate_manifest="$2" label="$3"; shift 3
  local expected actual
  expected="$(printf '%s\n' "$@" | LC_ALL=C sort -u)"
  actual="$(manifest_changed_paths "$base_manifest" "$candidate_manifest")"
  if [ "$actual" != "$expected" ]; then
    printf 'ERROR: unexpected change set for %s\nexpected:\n%s\nactual:\n%s\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  log "OK: ${label} changed exactly:"
  printf '%s\n' "$actual"
}

# Runtime symbol-resolution snippet. Every undefined symbol of every shared
# module must be provided by the candidate php executable's full library
# closure (php itself plus its transitive DT_NEEDED libraries). This accounts
# correctly for the fact that extensions resolve PHP/Zend symbols from the
# executable and libm/libc symbols from the executable's dependencies.
readonly SYMBOL_CHECK_SNIPPET='
set -eu
E=/usr/local/lib/php/extensions/no-debug-non-zts-20240924
{
  nm -D --defined-only /usr/local/bin/php | awk "{print \$NF}" | sed "s/@.*//"
  ldd /usr/local/bin/php | awk "/=>/{print \$3} /^\//{print \$1}" | while read -r lib; do
    nm -D --defined-only "$lib" 2>/dev/null | awk "{print \$NF}" | sed "s/@.*//"
  done
} | sort -u > /tmp/provided.syms
bad=0
for so in "$E"/*.so; do
  b=$(basename "$so")
  if ldd -r "$so" 2>&1 | grep -q "not found"; then echo "MISSING_LIB $b"; bad=1; fi
  for s in $(ldd -r "$so" 2>&1 | awk "/undefined symbol:/{print \$3}" | sort -u); do
    grep -qx "$s" /tmp/provided.syms || { echo "UNRESOLVED $b $s"; bad=1; }
  done
done
for exe in /usr/local/bin/php /usr/local/sbin/php-fpm; do
  if ldd -r "$exe" 2>&1 | grep -qE "undefined symbol|not found"; then echo "EXE_UNRESOLVED $exe"; bad=1; fi
done
exit $bad
'

# Run the symbol-resolution check inside an image (no network, entrypoint off).
container_symbol_check() {
  local image="$1"
  docker run --rm --platform "$BUILD_PLATFORM" --network none --entrypoint /bin/sh "$image" -c "$SYMBOL_CHECK_SNIPPET"
}
