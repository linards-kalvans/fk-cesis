#!/usr/bin/env bash
# Disposable, local-only application smoke for the Invoice Ninja PHP hotpatch.
#
# This script never contacts a remote Docker daemon, never pulls or pushes an
# image, never publishes a port, never mounts live data and never runs the
# image's normal entrypoint (init.sh -> supervisord -> workers/scheduler).
#
# It starts an ephemeral internal Docker network (no external egress), an
# ephemeral MariaDB with synthetic credentials, and the selected image with an
# overridden entrypoint. It then runs migrations, serves the login view on
# loopback inside the container, and generates a PDF from synthetic HTML with
# Snappdf. All containers, volumes and the network are removed on exit; no
# prune is ever run.
#
# Redis is not required: cache, session and queue drivers are forced to
# array/array/sync, so no external service or worker is started.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

VM_IMAGE_ID="sha256:68921270adf885a6fcedee6fde24851be517dd6d6b5579df731b688516c7d248"
IMAGE="$VM_IMAGE_ID"
MARIADB_IMAGE="mariadb:12.3.2"
SMOKE_PLATFORM="$BUILD_PLATFORM"

usage() {
  cat <<'EOF'
Usage: smoke-local.sh [--image IMAGE] [--mariadb-image IMAGE]

Defaults:
  --image          accepted local VM hotpatch image ID (never pulled)
  --mariadb-image  mariadb:12.3.2 (must already exist locally)

The smoke is disposable and local-only. It has no option to keep containers.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image) IMAGE="${2:?--image needs a value}"; shift 2 ;;
    --mariadb-image) MARIADB_IMAGE="${2:?--mariadb-image needs a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

preflight_local_docker

docker image inspect "$IMAGE" >/dev/null 2>&1 \
  || fail "image '$IMAGE' is not present locally; this smoke never pulls images"
docker image inspect "$MARIADB_IMAGE" >/dev/null 2>&1 \
  || fail "MariaDB image '$MARIADB_IMAGE' is not present locally; this smoke never pulls images"

RUN_ID="$(date +%s)-$$"
APP="fk-cesis-in-smoke-app-$RUN_ID"
DB="fk-cesis-in-smoke-db-$RUN_ID"
NET="fk-cesis-in-smoke-net-$RUN_ID"
VOL_STORAGE="fk-cesis-in-smoke-storage-$RUN_ID"
VOL_PUBLIC="fk-cesis-in-smoke-public-$RUN_ID"
TMPDIR="$(mktemp -d)"
APP_ENV_FILE="$TMPDIR/app.env"
DB_ENV_FILE="$TMPDIR/db.env"
umask 077

DB_ROOT="SMOKE_ONLY_NOT_A_REAL_ROOT_PASSWORD"
DB_PASS="SMOKE_ONLY_NOT_A_REAL_DB_PASSWORD"
# Synthetic, deterministic key material: 32 zero bytes. Never a live key.
APP_KEY="base64:$(head -c 32 /dev/zero | base64 -w0)"

cleanup() {
  local rc=$?
  set +e
  docker rm -fv "$APP" "$DB" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
  docker volume rm "$VOL_STORAGE" "$VOL_PUBLIC" >/dev/null 2>&1
  rm -rf "$TMPDIR"
  exit "$rc"
}
trap cleanup EXIT INT TERM

cat > "$DB_ENV_FILE" <<EOF
MARIADB_DATABASE=ninja
MARIADB_USER=ninja
MARIADB_PASSWORD=$DB_PASS
MARIADB_ROOT_PASSWORD=$DB_ROOT
EOF

cat > "$APP_ENV_FILE" <<EOF
APP_NAME=Smoke
APP_ENV=production
APP_KEY=$APP_KEY
APP_DEBUG=false
APP_URL=http://127.0.0.1:8099
LOG_CHANNEL=stderr
IS_DOCKER=true
REQUIRE_HTTPS=false
NINJA_ENVIRONMENT=selfhost
PDF_GENERATOR=snappdf
PHANTOMJS_PDF_GENERATION=false
CACHE_DRIVER=array
CACHE_STORE=array
SESSION_DRIVER=array
QUEUE_CONNECTION=sync
BROADCAST_DRIVER=log
BROADCAST_CONNECTION=log
MAIL_MAILER=log
FILESYSTEM_DISK=local
DB_CONNECTION=mysql
DB_HOST=$DB
DB_PORT=3306
DB_DATABASE=ninja
DB_USERNAME=ninja
DB_PASSWORD=$DB_PASS
DB_ROOT_PASSWORD=$DB_ROOT
HOME=/var/www
EOF

log "== static capability checks (no network, entrypoint overridden) =="
docker run --rm --platform "$SMOKE_PLATFORM" --network none --entrypoint /usr/local/sbin/php-fpm "$IMAGE" -t
docker run --rm -i --platform "$SMOKE_PLATFORM" --network none --entrypoint php "$IMAGE" <<'PHP'
<?php
if (PHP_VERSION !== '8.4.27') {
    fwrite(STDERR, 'unexpected PHP version: ' . PHP_VERSION . PHP_EOL);
    exit(1);
}
foreach (['exif', 'gd', 'intl', 'soap', 'imagick', 'saxonc'] as $extension) {
    if (!extension_loaded($extension)) {
        fwrite(STDERR, 'missing extension: ' . $extension . PHP_EOL);
        exit(1);
    }
}
echo 'PHP ' . PHP_VERSION . '; exif/gd/intl/soap/imagick/saxonc loaded' . PHP_EOL;
PHP

log "== Snappdf PDF from synthetic HTML (no network) =="
docker run --rm -i --platform "$SMOKE_PLATFORM" --network none --entrypoint php "$IMAGE" <<'PHP'
<?php
require '/var/www/html/vendor/autoload.php';

$pdf = (new \Beganovich\Snappdf\Snappdf())
    ->setChromiumPath('/usr/bin/google-chrome-stable')
    ->setHtml('<html><body><h1>Disposable smoke</h1><p>Synthetic HTML, not an invoice.</p></body></html>')
    ->generate();

if (!is_string($pdf) || substr($pdf, 0, 5) !== '%PDF-') {
    fwrite(STDERR, "PDF magic missing\n");
    exit(1);
}
echo 'PDF generated: ' . strlen($pdf) . ' bytes, magic ok' . PHP_EOL;
PHP

log "== supervisor configuration (inspected, never started) =="
worker_conf="$(docker run --rm --platform "$SMOKE_PLATFORM" --network none --entrypoint /bin/sh "$IMAGE" -c \
  'grep -E "^\[program:|^autostart=|^numprocs=" /etc/supervisor/conf.d/supervisord.conf')"
printf '%s\n' "$worker_conf"
for expected in '[program:queue-worker]' '[program:scheduler]' 'numprocs=2'; do
  printf '%s\n' "$worker_conf" | grep -Fq "$expected" \
    || fail "expected supervisor setting not found: $expected"
done

log "== disposable application stack on an internal network =="
docker network create --internal "$NET" >/dev/null
[ "$(docker network inspect -f '{{.Internal}}' "$NET")" = "true" ] \
  || fail "internal network was not created as internal"
docker volume create "$VOL_STORAGE" >/dev/null
docker volume create "$VOL_PUBLIC" >/dev/null

docker run -d --name "$DB" --platform "$SMOKE_PLATFORM" --network "$NET" \
  --env-file "$DB_ENV_FILE" "$MARIADB_IMAGE" >/dev/null

ready=0
for _ in $(seq 1 60); do
  if docker exec "$DB" mariadb-admin ping -h 127.0.0.1 -uroot -p"$DB_ROOT" --silent >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" = "1" ] || fail "disposable MariaDB did not become ready"
docker exec "$DB" mariadb -h 127.0.0.1 -uninja -p"$DB_PASS" -e 'SELECT 1' ninja >/dev/null 2>&1 \
  || fail "disposable MariaDB did not accept the synthetic application user"

docker run -d --name "$APP" --platform "$SMOKE_PLATFORM" --network "$NET" \
  --env-file "$APP_ENV_FILE" \
  -v "$VOL_STORAGE:/var/www/html/storage" \
  -v "$VOL_PUBLIC:/var/www/html/public" \
  --entrypoint /bin/sh "$IMAGE" -c 'sleep infinity' >/dev/null

[ "$(docker inspect -f '{{.Path}}' "$APP")" = "/bin/sh" ] \
  || fail "application container did not use the overridden entrypoint"
[ -z "$(docker port "$APP")" ] || fail "application container unexpectedly publishes a port"
[ -z "$(docker port "$DB")" ] || fail "MariaDB container unexpectedly publishes a port"
if docker top "$APP" | grep -Eq 'supervisord|queue:work|schedule:work'; then
  fail "worker or supervisord process started in the disposable application container"
fi

# Reproduce only the filesystem/bootstrap steps needed to serve the app. The
# normal init.sh path (migrations + cache/design/optimize + supervisord) is
# deliberately not executed.
docker exec -u root "$APP" sh -euc '
  mkdir -p /var/www/html/public \
    /var/www/html/storage/app/public \
    /var/www/html/storage/framework/sessions \
    /var/www/html/storage/framework/views \
    /var/www/html/storage/framework/cache \
    /var/www/html/storage/logs
  cp -a /tmp/public/. /var/www/html/public/
  chown -R www-data:www-data /var/www/html/public /var/www/html/storage
'

log "== migrations and synthetic account bootstrap against disposable MariaDB =="
docker exec -u www-data "$APP" php artisan migrate --force --no-interaction
docker exec -u www-data "$APP" php artisan db:seed --force --no-interaction >/dev/null
docker exec -u www-data "$APP" php artisan ninja:create-account \
  --email=smoke@example.invalid \
  --password=SMOKE_ONLY_NOT_A_REAL_LOGIN_PASSWORD >/dev/null

log "== login view over loopback inside the disposable container =="
docker exec -d -u www-data "$APP" sh -c \
  'cd /var/www/html && php artisan serve --host=127.0.0.1 --port=8099 >/tmp/serve.log 2>&1'
if ! docker exec -i -u www-data "$APP" php <<'PHP'
<?php
$code = 0;
$body = '';
for ($i = 0; $i < 60; $i++) {
    $ch = curl_init('http://127.0.0.1:8099/client/login');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 2,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    $body = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($code !== 0) {
        break;
    }
    usleep(500000);
}
if ($code !== 200) {
    fwrite(STDERR, 'login view status: ' . $code . PHP_EOL);
    exit(1);
}

if (stripos((string) $body, 'password') === false) {
    fwrite(STDERR, "login view did not contain a password field\n");
    exit(1);
}
echo 'GET /client/login => 200 (login view rendered; authenticated login not tested)' . PHP_EOL;
PHP
then
  log "== login smoke failed; last application log lines =="
  docker exec "$APP" sh -c 'tail -n 60 /var/www/html/storage/logs/laravel.log' >&2 || true
  exit 1
fi

log "== smoke complete (no external egress, no workers, no published ports) =="
