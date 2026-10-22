#!/usr/bin/env bash
# Verify a derived Invoice Ninja PHP 8.4.27 image against its approved base.
#
# Safety contract:
#   * accepts only the two approved digest-pinned bases;
#   * refuses a remote docker endpoint or a DOCKER_HOST override (fails closed);
#   * never reads .env or any credential material;
#   * the candidate must already exist locally and is NEVER pulled;
#   * every runtime check runs with --platform linux/amd64, --network none and an
#     overridden entrypoint, so /usr/local/bin/init.sh, supervisord, migrations
#     and any outbound mail/payment path can never execute;
#   * never mounts host/live volumes and never publishes ports;
#   * never pushes or prunes anything.
#
# It asserts: runtime/application/config equivalence (content + uid/gid/mode),
# exact file-change accounting, exact PHP release/extension versions, module-set
# equivalence, extension feature parity, eager (LD_BIND_NOW) symbol resolution
# and explicit ABI/load checks for the retained third-party extensions.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

BASE="${PROD_BASE_AMD64}"
CANDIDATE=""

usage() {
  cat <<'EOF'
Usage: verify.sh [--base <ref>] [--candidate <local-tag>]

  --base       approved base image reference (default: production amd64 child)
  --candidate  derived image tag to verify (default: fk-cesis-invoiceninja-php-hotpatch:8.4.27-<slug>)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --base)      [ $# -ge 2 ] || fail "--base needs a value";      BASE="$2"; shift 2 ;;
    --candidate) [ $# -ge 2 ] || fail "--candidate needs a value"; CANDIDATE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

resolved="$(resolve_base "$BASE")"
slug="${resolved%% *}"
rest="${resolved#* }"
build_base="${rest%% *}"
expected_base_php="${rest#* }"
[ -n "$CANDIDATE" ] || CANDIDATE="${CANDIDATE_REPO}:${PHP_HOTPATCH_VERSION}-${slug}"

preflight_local_docker

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The base is a public pinned image and may be pulled; the candidate must exist
# locally and is never pulled.
if ! docker image inspect "$build_base" >/dev/null 2>&1; then
  log "pulling public base image: ${build_base}"
  docker pull --platform "$BUILD_PLATFORM" "$build_base"
fi
docker image inspect "$CANDIDATE" >/dev/null 2>&1 \
  || fail "candidate image '${CANDIDATE}' is not present locally; refusing to pull it (build it with build-php.sh first)"

log "base (canonical amd64): ${build_base}"
log "candidate:              ${CANDIDATE}"

run_php() {
  local image="$1"; shift
  docker run --rm --platform "$BUILD_PLATFORM" --network none -e LD_BIND_NOW=1 \
    --entrypoint /usr/local/bin/php "$image" "$@"
}
run_fpm() {
  local image="$1"; shift
  docker run --rm --platform "$BUILD_PLATFORM" --network none -e LD_BIND_NOW=1 \
    --entrypoint /usr/local/sbin/php-fpm "$image" "$@"
}

# ---------------------------------------------------------------------------
# 1. Immutable image configuration / startup contract
# ---------------------------------------------------------------------------
log "== image configuration =="
cand_label_base="$(docker image inspect --format '{{index .Config.Labels "fk-cesis.php-hotpatch.base"}}' "$CANDIDATE")"
[ "$cand_label_base" = "$build_base" ] \
  || fail "candidate label fk-cesis.php-hotpatch.base='${cand_label_base}' does not match the selected base '${build_base}'"
log "OK: candidate base label matches the selected base"

cand_label_php="$(docker image inspect --format '{{index .Config.Labels "fk-cesis.php-hotpatch.php-version"}}' "$CANDIDATE")"
[ "$cand_label_php" = "$PHP_HOTPATCH_VERSION" ] \
  || fail "candidate label fk-cesis.php-hotpatch.php-version='${cand_label_php}' is not ${PHP_HOTPATCH_VERSION}"

for field in Entrypoint Cmd WorkingDir User; do
  b="$(docker image inspect --format "{{json .Config.${field}}}" "$build_base")"
  c="$(docker image inspect --format "{{json .Config.${field}}}" "$CANDIDATE")"
  [ "$b" = "$c" ] || fail "Config.${field} differs: base=${b} candidate=${c}"
  log "OK: Config.${field} unchanged: ${b}"
done

env_dump() {
  docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$1" \
    | grep -v -E '^PHP_(VERSION|URL|ASC_URL|SHA256)=' | LC_ALL=C sort || true
}
env_dump "$build_base" > "$WORK/env_base"
env_dump "$CANDIDATE" > "$WORK/env_cand"
diff -u "$WORK/env_base" "$WORK/env_cand" || fail "image Env differs outside the PHP version metadata"
log "OK: image Env identical apart from PHP version metadata"

cand_env="$(docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CANDIDATE")"
printf '%s\n' "$cand_env" | grep -qx "PHP_VERSION=${PHP_HOTPATCH_VERSION}" \
  || fail "candidate PHP_VERSION metadata is not ${PHP_HOTPATCH_VERSION}"
printf '%s\n' "$cand_env" | grep -qx "PHP_URL=${PHP_HOTPATCH_URL}" \
  || fail "candidate PHP_URL metadata is not the pinned 8.4.27 URL"
printf '%s\n' "$cand_env" | grep -qx "PHP_ASC_URL=${PHP_HOTPATCH_ASC_URL}" \
  || fail "candidate PHP_ASC_URL metadata is not the pinned 8.4.27 signature URL"
printf '%s\n' "$cand_env" | grep -qx "PHP_SHA256=${PHP_HOTPATCH_SHA256}" \
  || fail "candidate PHP_SHA256 metadata does not match the pinned hash"
log "OK: PHP_VERSION/PHP_URL/PHP_ASC_URL/PHP_SHA256 metadata match the rebuilt runtime"

# ---------------------------------------------------------------------------
# 2. Filesystem accounting (content + uid/gid/mode)
# ---------------------------------------------------------------------------
log "== filesystem accounting =="

manifest_for_trees() {
  # Rewrite the relative "./" paths into absolute paths so the combined
  # manifest can be compared against an absolute allowed-change set while the
  # path stays the third (H) / fifth (D/L/F) field of every line.
  local image="$1"; shift
  local tree
  for tree in "$@"; do
    container_manifest "$image" "$tree" | sed -E "s#(^| )\./#\1${tree}/#g"
  done
}

for tree in "${IDENTICAL_TREES[@]}"; do
  safe="$(echo "$tree" | tr '/' '_')"
  container_manifest "$build_base" "$tree" > "$WORK/base.$safe"
  container_manifest "$CANDIDATE"  "$tree" > "$WORK/cand.$safe"
  assert_no_changes "$WORK/base.$safe" "$WORK/cand.$safe" "tree ${tree}"
done

manifest_for_trees "$build_base" "${PHP_TREES[@]}" > "$WORK/php_base.manifest"
manifest_for_trees "$CANDIDATE"  "${PHP_TREES[@]}" > "$WORK/php_cand.manifest"
assert_only_allowed_changes "$WORK/php_base.manifest" "$WORK/php_cand.manifest" \
  "PHP runtime artifacts" "${ALLOWED_PHP_CHANGES[@]}"
assert_metadata_unchanged "$WORK/php_base.manifest" "$WORK/php_cand.manifest" \
  "PHP runtime artifacts"

# ---------------------------------------------------------------------------
# 3. Runtime checks (LD_BIND_NOW=1, --network none, entrypoint overridden)
# ---------------------------------------------------------------------------
log "== runtime checks (LD_BIND_NOW=1, --network none, entrypoint overridden) =="

base_php_version="$(run_php "$build_base" -r 'echo PHP_VERSION;')"
cand_php_version="$(run_php "$CANDIDATE" -r 'echo PHP_VERSION;')"
[ "$base_php_version" = "$expected_base_php" ] \
  || fail "base PHP version is ${base_php_version}, expected ${expected_base_php} for this approved base"
[ "$cand_php_version" = "$PHP_HOTPATCH_VERSION" ] \
  || fail "candidate PHP_VERSION constant is '${cand_php_version}', not exactly ${PHP_HOTPATCH_VERSION}"
log "base PHP_VERSION      : ${base_php_version}"
log "candidate PHP_VERSION : ${cand_php_version}"

run_php "$build_base" -v > "$WORK/base.phpv" 2>&1
run_php "$CANDIDATE"  -v > "$WORK/cand.phpv" 2>&1
grep -Eq '^PHP 8\.4\.27 \(cli\) ' "$WORK/cand.phpv" \
  || { sed -n '1p' "$WORK/cand.phpv" >&2; fail "candidate 'php -v' is not exactly PHP 8.4.27 (cli)"; }
if grep -Eq '^PHP 8\.5' "$WORK/cand.phpv"; then fail "candidate reports PHP 8.5, which is out of scope"; fi
log "OK: candidate 'php -v' first line: $(sed -n '1p' "$WORK/cand.phpv")"

run_fpm "$CANDIDATE" -v > "$WORK/cand.fpmv" 2>&1
grep -Eq '^PHP 8\.4\.27 \(fpm-fcgi\) ' "$WORK/cand.fpmv" \
  || { sed -n '1p' "$WORK/cand.fpmv" >&2; fail "candidate 'php-fpm -v' is not exactly PHP 8.4.27 (fpm-fcgi)"; }
log "OK: candidate 'php-fpm -v' first line: $(sed -n '1p' "$WORK/cand.fpmv")"

run_php "$CANDIDATE" -i > "$WORK/cand.phpinfo" 2>&1
grep -qx 'Thread Safety => disabled' "$WORK/cand.phpinfo" || fail "candidate is not a non-thread-safe (NTS) build"
grep -qx 'PHP Extension Build => API20240924,NTS' "$WORK/cand.phpinfo" || fail "candidate PHP Extension Build is not API20240924,NTS"
log "OK: candidate is amd64 NTS, API20240924"

run_php "$build_base" -n -m | LC_ALL=C sort > "$WORK/base.staticmods"
run_php "$CANDIDATE"  -n -m | LC_ALL=C sort > "$WORK/cand.staticmods"
diff -u "$WORK/base.staticmods" "$WORK/cand.staticmods" || fail "static (compiled-in) PHP module set differs between base and candidate"
log "OK: static PHP module set identical ($(grep -c . "$WORK/cand.staticmods") lines)"

run_php "$build_base" -m | LC_ALL=C sort > "$WORK/base.mods"
run_php "$CANDIDATE"  -m | LC_ALL=C sort > "$WORK/cand.mods"
diff -u "$WORK/base.mods" "$WORK/cand.mods" || fail "PHP module set differs between base and candidate"
log "OK: full PHP module set identical ($(grep -c . "$WORK/cand.mods") lines)"

cand_extdir="$(run_php "$CANDIDATE" -r 'echo PHP_EXTENSION_DIR;')"
[ "$cand_extdir" = "$PHP_EXT_DIR" ] || fail "unexpected extension dir: ${cand_extdir}"
log "OK: extension dir ${cand_extdir}"

printf '%s\n' "${BUNDLED_SHARED_MODULES[@]}" | sed 's/^opcache$/Zend OPcache/' | LC_ALL=C sort > "$WORK/bundled_names"
while read -r name; do
  run_php "$CANDIDATE" -r "exit(extension_loaded('${name}') ? 0 : 1);" || fail "bundled module '${name}' failed to load"
done < "$WORK/bundled_names"
log "OK: all bundled shared modules load: $(printf '%s ' "${BUNDLED_SHARED_MODULES[@]}")"

run_php "$CANDIDATE" -r 'exit((extension_loaded("imagick") && extension_loaded("saxonc")) ? 0 : 1);' \
  || fail "retained third-party modules imagick/saxonc failed to load"
[ "$(run_php "$CANDIDATE" -r 'echo phpversion("imagick");')" = "3.8.1" ] || fail "imagick is not exactly 3.8.1"
[ "$(run_php "$CANDIDATE" -r 'echo phpversion("saxonc");')" = "12.5" ] || fail "saxonc is not exactly 12.5"
log "OK: retained imagick 3.8.1 and saxonc 12.5 load"

extver() {
  run_php "$1" -r 'foreach (get_loaded_extensions() as $e) { printf("%s=%s\n", $e, phpversion($e)); }' | LC_ALL=C sort
}
extver "$build_base" > "$WORK/base.extver"
extver "$CANDIDATE"  > "$WORK/cand.extver"
sed -e "s/${base_php_version}$/PHPRELEASE/" "$WORK/base.extver" > "$WORK/base.extver.norm"
sed -e "s/${cand_php_version}$/PHPRELEASE/" "$WORK/cand.extver" > "$WORK/cand.extver.norm"
diff -u "$WORK/base.extver.norm" "$WORK/cand.extver.norm" \
  || fail "extension versions differ beyond the PHP release bump"
log "OK: every extension version matches the base (or tracks the 8.4.27 release)"

feature_fingerprint() {
  run_php "$1" -i | grep -E '^(GD Version|FreeType Support|FreeType Linkage|FreeType Version|GIF Read Support|GIF Create Support|JPEG Support|libJPEG Version|PNG Support|libPNG Version|WBMP Support|XPM Support|libXpm Version|XBM Support|WebP Support|BMP Support|AVIF Support|TGA Read Support|ICU version|ICU Data version|ICU TZData version|ICU Unicode version|Zip version|Libzip version) =>' | LC_ALL=C sort
}
feature_fingerprint "$build_base" > "$WORK/base.features"
feature_fingerprint "$CANDIDATE"  > "$WORK/cand.features"
diff -u "$WORK/base.features" "$WORK/cand.features" \
  || fail "bundled extension feature set differs (gd/intl/zip)"
log "OK: gd/intl/zip feature parity with base"
sed -n '1,40p' "$WORK/cand.features" | sed 's/^/    /'

run_fpm "$CANDIDATE" -t > "$WORK/phpfpm.t" 2>&1 \
  || { cat "$WORK/phpfpm.t" >&2; fail "php-fpm configuration test failed"; }
grep -q 'test is successful' "$WORK/phpfpm.t" || { cat "$WORK/phpfpm.t" >&2; fail "php-fpm -t did not report success"; }
log "OK: php-fpm configuration test successful"

# ---------------------------------------------------------------------------
# 4. Eager symbol resolution (LD_BIND_NOW) + ldd -r accounting
# ---------------------------------------------------------------------------
log "== symbol resolution =="
container_symbol_check "$build_base" > "$WORK/sym_base" 2>&1 \
  || { cat "$WORK/sym_base" >&2; fail "symbol check unexpectedly failed on the approved base"; }
container_symbol_check "$CANDIDATE" > "$WORK/sym_cand" 2>&1 \
  || { cat "$WORK/sym_cand" >&2; fail "candidate has unresolved symbols or missing libraries"; }
log "OK: all shared modules resolve against the candidate php library closure (ldd -r)"

log "== verification complete =="
log "candidate id: $(docker image inspect --format '{{.Id}}' "$CANDIDATE")"
