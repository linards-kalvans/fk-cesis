# syntax=docker/dockerfile:1

# Derived Invoice Ninja image that upgrades ONLY the PHP patch level to 8.4.27.
#
# PHP 8.4.27 fixes CVE-2026-109618 and CVE-2026-109619. The upstream fix
# (php-src 31c0ea7d7ff1d1fccb6492e52dab544011628065, "Avoid state corruption via
# bailout") touches ext/exif, ext/gd, ext/intl, ext/soap and the Zend engine.
# Every bundled shared extension is therefore rebuilt from the same verified
# 8.4.27 source; only the third-party imagick 3.8.1 and saxonc 12.5 modules are
# retained from the base and verified by explicit load/ABI checks.
#
# Everything else is inherited byte-for-byte from the digest-pinned base image:
# the Invoice Ninja application tree (/var/www/html), /tmp/public, the container
# entrypoint, the supervisord configuration, the PHP ini/FPM configuration and
# every system and runtime library.
#
# The builder stage starts FROM the very same pinned base so that the retained
# third-party modules are present and left untouched when the source-built
# modules are staged into the final image. This avoids copying an unrelated
# /usr/local tree from an official php image.
#
# This recipe is intentionally amd64-specific: both approved bases are
# linux/amd64 and the captured configure options contain x86_64-linux-gnu.
#
# Scope note on build-time tooling: /usr/local/bin/phpize, /usr/local/bin/php-config,
# /usr/local/bin/pecl, /usr/local/bin/pear and /usr/local/include/php are NOT copied
# into the final image; they stay at the base's 8.4.x and are outside the runtime
# contract (nothing in the Invoice Ninja runtime invokes them). This is deliberate
# rather than a broad copy of the build tree.

ARG BASE_IMAGE=invoiceninja/invoiceninja-debian@sha256:f938079be2b24df0fe5f1478c281df9011c658f3ad46fc02173bc578bb923fe0

# ---------------------------------------------------------------------------
# Builder: compile PHP 8.4.27 from the verified upstream source.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS php-builder

ARG BASE_IMAGE

# Fail loudly unless the base is one of the two approved digests, is linux/amd64
# and is a non-thread-safe build of the expected base PHP release. The host
# driver (build-php.sh / verify.sh) additionally refuses a remote docker
# endpoint; a Dockerfile cannot perform that daemon preflight itself.
RUN set -eux; \
    case "${BASE_IMAGE}" in \
        "invoiceninja/invoiceninja-debian@sha256:f938079be2b24df0fe5f1478c281df9011c658f3ad46fc02173bc578bb923fe0") expected_base_php="8.4.22" ;; \
        "invoiceninja/invoiceninja-debian@sha256:587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd") expected_base_php="8.4.20" ;; \
        *) echo "refusing unapproved BASE_IMAGE: ${BASE_IMAGE}" >&2; exit 1 ;; \
    esac; \
    [ "$(uname -m)" = "x86_64" ] || { echo "only linux/amd64 is supported" >&2; exit 1; }; \
    php -r "exit(PHP_VERSION === '${expected_base_php}' ? 0 : 1);"; \
    php -i | grep -qx 'Thread Safety => disabled'; \
    php -i | grep -qx 'PHP Extension Build => API20240924,NTS'

# NOTE: the base image already defines ENV PHP_VERSION / PHP_URL / PHP_SHA256
# (pointing at its own older release). Docker always lets ENV win over a
# same-named ARG, so the hotpatch values deliberately use distinct names and
# the final stage re-declares the canonical PHP_* metadata.
ARG HOTPATCH_PHP_VERSION=8.4.27
ARG HOTPATCH_PHP_URL=https://www.php.net/distributions/php-8.4.27.tar.xz
ARG HOTPATCH_PHP_SHA256=dcf93923b0e38e0d5252b25b796520b5a47761a08b3488b6d0b5d1115764d3f0
ARG JOBS=2
ARG EXT_DIR=/usr/local/lib/php/extensions/no-debug-non-zts-20240924
ARG BUNDLED_MODULES="bcmath exif gd intl opcache pcntl pdo_mysql soap sodium zip"

# Snapshot the inherited PHP artifacts before touching anything. Used later to
# prove that the rebuild replaces only the bundled shared modules and that make
# install does not rewrite the existing ini/FPM configs.
RUN set -eux; \
    mkdir -p /hotpatch; \
    ls -1 "$EXT_DIR" | LC_ALL=C sort > /hotpatch/ext-before.list; \
    for m in $BUNDLED_MODULES; do grep -qx "$m.so" /hotpatch/ext-before.list; done; \
    ( cd "$EXT_DIR"; find . -maxdepth 1 -type f -name '*.so' -exec sha256sum {} + | LC_ALL=C sort -k2 ) > /hotpatch/ext-before.sha256; \
    find /usr/local/etc -type f -exec sha256sum {} + | LC_ALL=C sort > /hotpatch/etc-before.sha256

# Public build dependencies only. No Invoice Ninja runtime package is removed
# and the builder stage is discarded, so runtime dependencies are unaffected.
# The gd/intl/zip packages mirror the per-extension options the base used.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        $PHPIZE_DEPS \
        ca-certificates \
        curl \
        xz-utils \
        libargon2-dev \
        libcurl4-openssl-dev \
        libonig-dev \
        libreadline-dev \
        libsodium-dev \
        libsqlite3-dev \
        libssl-dev \
        libxml2-dev \
        zlib1g-dev \
        libfreetype6-dev \
        libjpeg62-turbo-dev \
        libpng-dev \
        libxpm-dev \
        libwebp-dev \
        libavif-dev \
        libaom-dev \
        libdav1d-dev \
        libicu-dev \
        libzip-dev \
        libbz2-dev \
    ; \
    apt-get dist-clean

# Fetch, integrity-check (SHA256 pinned in this file) and build the source with
# the base's exact global configure options plus matching per-extension options
# that reproduce the base's bundled shared extension set.
RUN set -eux; \
    mkdir -p /usr/src; \
    cd /usr/src; \
    curl -fsSL -o php.tar.xz "$HOTPATCH_PHP_URL"; \
    echo "$HOTPATCH_PHP_SHA256 *php.tar.xz" | sha256sum -c -; \
    tar -xJf php.tar.xz; \
    rm -f php.tar.xz; \
    test -d "php-$HOTPATCH_PHP_VERSION"; \
    cd "php-$HOTPATCH_PHP_VERSION"; \
    if [ ! -d /usr/include/curl ] && [ ! -e /usr/local/include/curl ]; then \
        ln -sT /usr/include/x86_64-linux-gnu/curl /usr/local/include/curl; \
    fi; \
    export \
        CFLAGS="$PHP_CFLAGS" \
        CPPFLAGS="$PHP_CPPFLAGS" \
        LDFLAGS="$PHP_LDFLAGS" \
        PHP_BUILD_PROVIDER='https://github.com/docker-library/php' \
        PHP_UNAME='Linux - Docker' \
    ; \
    ./configure \
        --build=x86_64-linux-gnu \
        --sysconfdir=/usr/local/etc \
        --with-config-file-path=/usr/local/etc/php \
        --with-config-file-scan-dir=/usr/local/etc/php/conf.d \
        --enable-option-checking=fatal \
        --with-mhash \
        --with-pic \
        --enable-mbstring \
        --enable-mysqlnd \
        --with-password-argon2 \
        --with-sodium=shared \
        --with-pdo-sqlite=/usr \
        --with-sqlite3=/usr \
        --with-curl \
        --with-iconv \
        --with-openssl \
        --with-readline \
        --with-zlib \
        --disable-phpdbg \
        --with-pear \
        --with-libdir=lib/x86_64-linux-gnu \
        --disable-cgi \
        --enable-fpm \
        --with-fpm-user=www-data \
        --with-fpm-group=www-data \
        --enable-bcmath=shared \
        --enable-exif=shared \
        --enable-gd=shared --with-webp --with-jpeg --with-xpm --with-freetype --with-avif \
        --enable-intl=shared \
        --enable-opcache=shared \
        --enable-pcntl=shared \
        --with-pdo-mysql=shared,mysqlnd \
        --enable-soap=shared \
        --with-zip=shared \
    ; \
    make -j"$JOBS"; \
    find -type f -name '*.a' -delete; \
    make install; \
    make clean; \
    strip --strip-all /usr/local/bin/php /usr/local/sbin/php-fpm; \
    for m in $BUNDLED_MODULES; do strip --strip-all "$EXT_DIR/$m.so"; done

# Fail loudly unless: the rebuilt runtime is exactly 8.4.27; every bundled
# module loads; the retained third-party modules still load; make install did
# not rewrite any pre-existing ini/FPM config; the shared extension set is
# unchanged; and only the bundled modules differ from the inherited ones.
RUN set -eux; \
    php --version; \
    php -r 'exit(PHP_VERSION === "8.4.27" ? 0 : 1);'; \
    php -r 'exit(PHP_EXTENSION_DIR === "/usr/local/lib/php/extensions/no-debug-non-zts-20240924" ? 0 : 1);'; \
    php -r 'foreach (explode(" ", getenv("BUNDLED_MODULES")) as $m) { $n = ($m === "opcache") ? "Zend OPcache" : $m; if (!extension_loaded($n)) { fwrite(STDERR, "not loaded: $n\n"); exit(1); } }'; \
    php -r 'exit((extension_loaded("imagick") && extension_loaded("saxonc")) ? 0 : 1);'; \
    php-fpm -v; \
    while read -r hash path; do \
        echo "$hash  $path" | sha256sum -c -; \
    done < /hotpatch/etc-before.sha256; \
    ( cd "$EXT_DIR"; find . -maxdepth 1 -type f -name '*.so' -exec sha256sum {} + | LC_ALL=C sort -k2 ) > /hotpatch/ext-after.sha256; \
    ls -1 "$EXT_DIR" | LC_ALL=C sort > /hotpatch/ext-after.list; \
    diff -u /hotpatch/ext-before.list /hotpatch/ext-after.list; \
    diff /hotpatch/ext-before.sha256 /hotpatch/ext-after.sha256 | sed -n 's/^[<>] //p' | awk '{print $NF}' | LC_ALL=C sort -u > /hotpatch/ext-changed.txt || true; \
    for m in $BUNDLED_MODULES; do echo "./$m.so"; done | LC_ALL=C sort > /hotpatch/ext-expected.txt; \
    diff -u /hotpatch/ext-expected.txt /hotpatch/ext-changed.txt

# ---------------------------------------------------------------------------
# Final: the pinned base with only the rebuilt PHP runtime artifacts replaced.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS final

ARG BASE_IMAGE
ARG EXT_DIR=/usr/local/lib/php/extensions/no-debug-non-zts-20240924

LABEL fk-cesis.php-hotpatch.php-version="8.4.27" \
      fk-cesis.php-hotpatch.cves="CVE-2026-109618,CVE-2026-109619" \
      fk-cesis.php-hotpatch.base="${BASE_IMAGE}"

COPY --from=php-builder /usr/local/bin/php /usr/local/bin/php
COPY --from=php-builder /usr/local/sbin/php-fpm /usr/local/sbin/php-fpm
COPY --from=php-builder ${EXT_DIR}/ ${EXT_DIR}/

# Keep the inherited PHP build metadata consistent with the rebuilt runtime.
ENV PHP_VERSION=8.4.27 \
    PHP_URL=https://www.php.net/distributions/php-8.4.27.tar.xz \
    PHP_ASC_URL=https://www.php.net/distributions/php-8.4.27.tar.xz.asc \
    PHP_SHA256=dcf93923b0e38e0d5252b25b796520b5a47761a08b3488b6d0b5d1115764d3f0

# ENTRYPOINT, CMD, WORKDIR, EXPOSE and all configuration files are inherited
# from the base image and intentionally left untouched.
