#!/usr/bin/env bash
# Build a local-only derived Invoice Ninja image with PHP upgraded to 8.4.27.
#
# Safety contract:
#   * accepts only the two approved digest-pinned bases (no :latest / floating tags);
#   * refuses a remote docker endpoint or a DOCKER_HOST override;
#   * never reads .env or any credential material;
#   * never mounts host/live volumes, publishes ports, or uses host networking;
#   * never runs the Invoice Ninja entrypoint or application bootstrap;
#   * tags the result for local use only and never pushes.
#
# Network access is used only to fetch public build dependencies and the
# pinned PHP source tarball (integrity-checked by SHA256 in the Dockerfile).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

BASE="${PROD_BASE_AMD64}"
TAG=""
JOBS="2"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: build-php.sh [--base <ref>] [--tag <local-tag>] [--jobs N] [--dry-run]

  --base   approved base image reference (default: production amd64 child)
  --tag    local-only image tag (default: fk-cesis-invoiceninja-php-hotpatch:8.4.27-<slug>)
  --jobs   parallel compile jobs, kept small on purpose (default: 2)
  --dry-run  print the docker build command without executing it
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --base)   [ $# -ge 2 ] || fail "--base needs a value";   BASE="$2"; shift 2 ;;
    --tag)    [ $# -ge 2 ] || fail "--tag needs a value";    TAG="$2";  shift 2 ;;
    --jobs)   [ $# -ge 2 ] || fail "--jobs needs a value";   JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

case "$JOBS" in
  ''|*[!0-9]*) fail "--jobs must be a positive integer (got '${JOBS}')" ;;
esac
[ "$JOBS" -ge 1 ] || fail "--jobs must be >= 1"
[ "$JOBS" -le "$MAX_JOBS" ] || fail "--jobs must be <= ${MAX_JOBS} to avoid overloading the host (got ${JOBS})"

resolved="$(resolve_base "$BASE")"
slug="${resolved%% *}"
rest="${resolved#* }"
build_base="${rest%% *}"

[ -n "$TAG" ] || TAG="${CANDIDATE_REPO}:${PHP_HOTPATCH_VERSION}-${slug}"
case "$TAG" in
  */*) fail "refusing tag '${TAG}': local-only tags must not name a registry" ;;
esac

cmd=(docker build
  --platform "$BUILD_PLATFORM"
  --file "$SCRIPT_DIR/Dockerfile"
  --build-arg "BASE_IMAGE=${build_base}"
  --build-arg "JOBS=${JOBS}"
  --tag "$TAG"
  "$SCRIPT_DIR")

if [ "$DRY_RUN" = 1 ]; then
  printf 'DRY RUN:'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  exit 0
fi

preflight_local_docker

log "base (canonical amd64): ${build_base}"
log "tag (local only):       ${TAG}"
log "compile jobs:           ${JOBS}"
"${cmd[@]}"

log "built image id: $(docker image inspect --format '{{.Id}}' "$TAG")"
log "next: ./verify.sh --base '${BASE}' --candidate '${TAG}'"
