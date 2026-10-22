#!/usr/bin/env python3
"""Contract tests for the Invoice Ninja PHP 8.4.27 hotpatch preparation.

These tests are hermetic: they never touch a Docker daemon, never read
credentials and never use the network. Behavioural checks run the shell entry
points with a fake ``docker`` executable placed first on ``PATH``.

Uses only the Python standard library (unittest, pathlib, subprocess, ...).
"""

import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOTPATCH_DIR = REPO_ROOT / "docker" / "invoiceninja-php-hotpatch"
DOCKERFILE = HOTPATCH_DIR / "Dockerfile"
COMMON = HOTPATCH_DIR / "common.sh"
BUILD = HOTPATCH_DIR / "build-php.sh"
VERIFY = HOTPATCH_DIR / "verify.sh"

PROD_BASE_INDEX = (
    "invoiceninja/invoiceninja-debian@sha256:"
    "293ada121c633096e387fc7103b221a2c2a2aee95b8d9ef34991bf57de8f505b"
)
PROD_BASE_AMD64 = (
    "invoiceninja/invoiceninja-debian@sha256:"
    "f938079be2b24df0fe5f1478c281df9011c658f3ad46fc02173bc578bb923fe0"
)
VM_BASE_INDEX = (
    "invoiceninja/invoiceninja-debian@sha256:"
    "673fac38a57de324e120d57dd0c05d35d9a914bac588e9a9438a19a3c74feebc"
)
VM_BASE_AMD64 = (
    "invoiceninja/invoiceninja-debian@sha256:"
    "587fb74909ab605f4215c6c64b8df0552dd468044d66eec24c9e135b8ca3e9cd"
)
PHP_VERSION = "8.4.27"
PHP_URL = "https://www.php.net/distributions/php-8.4.27.tar.xz"
PHP_SHA256 = "dcf93923b0e38e0d5252b25b796520b5a47761a08b3488b6d0b5d1115764d3f0"
EXT_DIR = "/usr/local/lib/php/extensions/no-debug-non-zts-20240924"

# Every bundled shared module present in both approved bases. All must be
# rebuilt from the 8.4.27 source; only imagick/saxon are retained.
BASELINE_SHARED_MODULES = [
    "bcmath", "exif", "gd", "imagick", "intl", "opcache",
    "pcntl", "pdo_mysql", "saxon", "soap", "sodium", "zip",
]
BUNDLED_SHARED_MODULES = [
    "bcmath", "exif", "gd", "intl", "opcache",
    "pcntl", "pdo_mysql", "soap", "sodium", "zip",
]
RETAINED_THIRD_PARTY_MODULES = ["imagick", "saxon"]

# Base global configure options plus the per-extension options that reproduce
# the base's bundled shared extension set.
CONFIGURE_OPTIONS = [
    "--build=x86_64-linux-gnu",
    "--sysconfdir=/usr/local/etc",
    "--with-config-file-path=/usr/local/etc/php",
    "--with-config-file-scan-dir=/usr/local/etc/php/conf.d",
    "--enable-option-checking=fatal",
    "--with-mhash",
    "--with-pic",
    "--enable-mbstring",
    "--enable-mysqlnd",
    "--with-password-argon2",
    "--with-sodium=shared",
    "--with-pdo-sqlite=/usr",
    "--with-sqlite3=/usr",
    "--with-curl",
    "--with-iconv",
    "--with-openssl",
    "--with-readline",
    "--with-zlib",
    "--disable-phpdbg",
    "--with-pear",
    "--with-libdir=lib/x86_64-linux-gnu",
    "--disable-cgi",
    "--enable-fpm",
    "--with-fpm-user=www-data",
    "--with-fpm-group=www-data",
    "--enable-bcmath=shared",
    "--enable-exif=shared",
    "--enable-gd=shared",
    "--with-webp",
    "--with-jpeg",
    "--with-xpm",
    "--with-freetype",
    "--with-avif",
    "--enable-intl=shared",
    "--enable-opcache=shared",
    "--enable-pcntl=shared",
    "--with-pdo-mysql=shared,mysqlnd",
    "--enable-soap=shared",
    "--with-zip=shared",
]

ALLOWED_PHP_CHANGES = (
    ["/usr/local/bin/php", "/usr/local/sbin/php-fpm"]
    + [f"{EXT_DIR}/{m}.so" for m in BUNDLED_SHARED_MODULES]
)


def _read(path: pathlib.Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing required file: {path}")
    return path.read_text()


def _bash(args, cwd=None, env=None):
    return subprocess.run(["bash", *args], cwd=cwd, env=env, capture_output=True, text=True)


def _bash_n(path: pathlib.Path):
    return subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)


def _code_lines(content: str):
    """Return non-comment, non-blank lines (comment prose must not fail safety checks)."""
    return [
        line
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _fake_docker_env(tmpdir: pathlib.Path, extra_env=None):
    """Return an env with a fake ``docker`` first on PATH and a call log."""
    bindir = tmpdir / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    log = tmpdir / "docker.log"
    fake = bindir / "docker"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >> "${FAKE_DOCKER_LOG:?}"\n'
        'case "$1" in\n'
        '  context) case "${FAKE_CONTEXT_MODE:-unix}" in\n'
        "             unix) printf 'unix:///var/run/docker.sock\\n' ;;\n"
        "             empty) printf '\\n' ;;\n"
        "             fail) exit 2 ;;\n"
        "           esac; exit 0 ;;\n"
        '  image) [ -n "${FAKE_IMAGE_MISSING:-}" ] && exit 1; exit 0 ;;\n'
        '  *) exit 0 ;;\n'
        "esac\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ)
    for var in ("DOCKER_HOST", "BUILDKIT_HOST", "BUILDX_BUILDER", "DOCKER_CONTEXT"):
        env.pop(var, None)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_DOCKER_LOG"] = str(log)
    if extra_env:
        env.update(extra_env)
    return env, log


def _log_lines(log: pathlib.Path):
    if not log.exists():
        return []
    return [ln for ln in log.read_text().splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Dockerfile contracts
# ---------------------------------------------------------------------------


class TestDockerfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(DOCKERFILE)

    def test_default_base_is_prod_amd64_child_digest(self):
        self.assertIn(f"ARG BASE_IMAGE={PROD_BASE_AMD64}", self.content)

    def test_both_stages_from_pinned_base_arg(self):
        self.assertEqual(self.content.count("FROM ${BASE_IMAGE} AS"), 2)

    def test_no_mutable_or_unapproved_php_bases(self):
        for forbidden in (":latest", "php:8.5", "php:latest", "php:8.4-fpm", "php:8.4"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.content)

    def test_asserts_approved_base_and_expected_versions(self):
        for ref in (PROD_BASE_AMD64, VM_BASE_AMD64):
            with self.subTest(ref=ref):
                self.assertIn(ref, self.content)
        self.assertIn('expected_base_php="8.4.22"', self.content)
        self.assertIn('expected_base_php="8.4.20"', self.content)
        self.assertIn("refusing unapproved BASE_IMAGE", self.content)

    def test_asserts_amd64_and_nts(self):
        self.assertIn('[ "$(uname -m)" = "x86_64" ]', self.content)
        self.assertIn("grep -qx 'Thread Safety => disabled'", self.content)
        self.assertIn("grep -qx 'PHP Extension Build => API20240924,NTS'", self.content)

    def test_explains_driver_only_daemon_preflight(self):
        self.assertIn("docker", self.content)
        self.assertIn("endpoint", self.content)
        self.assertIn("preflight", self.content)

    def test_pins_target_version_url_and_hash(self):
        self.assertIn(f"ARG HOTPATCH_PHP_VERSION={PHP_VERSION}", self.content)
        self.assertIn(f"ARG HOTPATCH_PHP_URL={PHP_URL}", self.content)
        self.assertIn(f"ARG HOTPATCH_PHP_SHA256={PHP_SHA256}", self.content)

    def test_enforces_source_sha256(self):
        self.assertIn('echo "$HOTPATCH_PHP_SHA256 *php.tar.xz" | sha256sum -c -', self.content)

    def test_asserts_runtime_version_post_build(self):
        self.assertIn('exit(PHP_VERSION === "8.4.27" ? 0 : 1);', self.content)

    def test_contains_every_configure_option(self):
        for opt in CONFIGURE_OPTIONS:
            with self.subTest(option=opt):
                self.assertIn(opt, self.content)

    def test_bounded_compile_jobs(self):
        self.assertIn("ARG JOBS=2", self.content)
        self.assertIn('make -j"$JOBS"', self.content)

    def test_declares_all_bundled_modules(self):
        for m in BUNDLED_SHARED_MODULES:
            with self.subTest(module=m):
                self.assertIn(m, self.content)

    def test_builds_gd_with_matching_deps(self):
        for pkg in (
            "libfreetype6-dev",
            "libjpeg62-turbo-dev",
            "libpng-dev",
            "libxpm-dev",
            "libwebp-dev",
            "libavif-dev",
            "libaom-dev",
            "libdav1d-dev",
            "libicu-dev",
            "libzip-dev",
            "libbz2-dev",
        ):
            with self.subTest(pkg=pkg):
                self.assertIn(pkg, self.content)

    def test_copies_only_php_runtime_artifacts(self):
        self.assertIn("COPY --from=php-builder /usr/local/bin/php /usr/local/bin/php", self.content)
        self.assertIn(
            "COPY --from=php-builder /usr/local/sbin/php-fpm /usr/local/sbin/php-fpm",
            self.content,
        )
        self.assertIn("COPY --from=php-builder ${EXT_DIR}/ ${EXT_DIR}/", self.content)

    def test_does_not_copy_php_configuration_or_build_tooling(self):
        self.assertNotIn("COPY --from=php-builder /usr/local/etc", self.content)
        self.assertNotIn("COPY --from=php-builder /usr/local/include", self.content)
        self.assertIn("php-config", self.content)  # documented scope note only

    def test_does_not_override_entrypoint_or_cmd(self):
        for line in self.content.splitlines():
            stripped = line.strip()
            self.assertFalse(stripped.startswith("ENTRYPOINT "), stripped)
            self.assertFalse(stripped.startswith("CMD "), stripped)

    def test_no_application_bootstrap_in_build(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in ("init.sh", "supervisord", "artisan", "migrate", "queue:work"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_sets_rebuilt_php_metadata(self):
        self.assertIn(f"PHP_VERSION={PHP_VERSION}", self.content)
        self.assertIn(f"PHP_SHA256={PHP_SHA256}", self.content)

    def test_extension_accounting_guard_present(self):
        self.assertIn("ext-changed.txt", self.content)
        self.assertIn("ext-expected.txt", self.content)
        self.assertIn('for m in $BUNDLED_MODULES; do echo "./$m.so"; done', self.content)

    def test_guards_existing_configs_are_not_rewritten(self):
        self.assertIn("etc-before.sha256", self.content)
        self.assertIn("sha256sum -c -", self.content)

    def test_strip_is_scoped_to_built_artifacts(self):
        self.assertIn("strip --strip-all /usr/local/bin/php /usr/local/sbin/php-fpm", self.content)
        self.assertIn('for m in $BUNDLED_MODULES; do strip --strip-all "$EXT_DIR/$m.so"; done', self.content)
        self.assertNotIn("find /usr/local -type f -perm", self.content)


# ---------------------------------------------------------------------------
# common.sh: allowlist, module inventory and manifest accounting
# ---------------------------------------------------------------------------


class TestCommonScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(COMMON)

    def test_bash_syntax(self):
        result = _bash_n(COMMON)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_declares_target_constants(self):
        self.assertIn(f'PHP_HOTPATCH_VERSION="{PHP_VERSION}"', self.content)
        self.assertIn(f'PHP_HOTPATCH_SHA256="{PHP_SHA256}"', self.content)
        self.assertIn(PHP_URL, self.content)

    def test_declares_both_approved_bases(self):
        for ref in (PROD_BASE_INDEX, PROD_BASE_AMD64, VM_BASE_INDEX, VM_BASE_AMD64):
            with self.subTest(ref=ref):
                self.assertIn(ref, self.content)

    def test_no_retained_bundled_module(self):
        """All baseline shared modules are rebuilt except imagick/saxon."""
        self.assertIn(
            "readonly BUNDLED_SHARED_MODULES=(bcmath exif gd intl opcache pcntl pdo_mysql soap sodium zip)",
            self.content,
        )
        self.assertIn("readonly RETAINED_THIRD_PARTY_MODULES=(imagick saxon)", self.content)
        self.assertEqual(sorted(BUNDLED_SHARED_MODULES + RETAINED_THIRD_PARTY_MODULES),
                         sorted(BASELINE_SHARED_MODULES))

    def test_allowed_change_set_covers_all_bundled_and_no_third_party(self):
        for path in ALLOWED_PHP_CHANGES:
            with self.subTest(path=path):
                self.assertIn(path, self.content)
        for m in RETAINED_THIRD_PARTY_MODULES:
            with self.subTest(retained=m):
                self.assertNotIn(f'"/usr/local/lib/php/extensions/no-debug-non-zts-20240924/{m}.so"',
                                 self.content)

    def test_allowlisted_change_set_is_exactly_twelve(self):
        """Assert the real sourced array, so an extra allowed path fails."""
        result = _bash(["-c", f'. "{COMMON}"; printf "%s\\n" "${{ALLOWED_PHP_CHANGES[@]}}"'])
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = sorted(result.stdout.split())
        self.assertEqual(actual, sorted(ALLOWED_PHP_CHANGES))
        self.assertEqual(len(actual), 12)

    def test_runtime_helpers_are_mount_and_port_free(self):
        result = _bash(["-c", f'. "{COMMON}"; declare -f container_manifest container_symbol_check'])
        self.assertEqual(result.returncode, 0, result.stderr)
        body = result.stdout
        for forbidden in (" --volume", " -v ", " --publish", " -p ", "--network host", "--privileged"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)
        self.assertIn("--network none", body)
        self.assertIn("--entrypoint", body)
        self.assertIn("--platform", body)

    def test_manifest_fails_nonzero_on_missing_tree(self):
        missing = "/nonexistent-fk-cesis-hotpatch-manifest"
        result = _bash(["-c", f'. "{COMMON}"; sh -c "$MANIFEST_SNIPPET" sh "{missing}"'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISSING_TREE", result.stderr)
        self.assertNotIn('echo "MISSING_TREE $1"; exit 0', self.content)

    def test_manifest_succeeds_on_existing_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "f").write_text("x")
            result = _bash(["-c", f'. "{COMMON}"; sh -c "$MANIFEST_SNIPPET" sh "{tmp}"'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("./f", result.stdout)
            self.assertIn("H ", result.stdout)

    def test_manifest_records_uid_gid_mode(self):
        self.assertIn('find . -xdev -type f -printf "F %u %g %m %p\\n"', self.content)
        self.assertIn('find . -xdev -type d -printf "D %u %g %m %p\\n"', self.content)
        self.assertIn('find . -xdev -type l -printf "L %u %g %m %p -> %l\\n"', self.content)
        self.assertIn("manifest_meta", self.content)

    def test_symbol_check_snippet_present(self):
        self.assertIn("SYMBOL_CHECK_SNIPPET", self.content)
        self.assertIn("nm -D --defined-only /usr/local/bin/php", self.content)
        self.assertIn("ldd -r", self.content)

    def test_fails_closed_on_context_inspection_failure(self):
        self.assertIn("could not inspect the active docker context", self.content)
        self.assertIn("endpoint is empty", self.content)

    def _resolve(self, ref):
        return _bash(["-c", f'. "{COMMON}"; resolve_base "{ref}"'])

    def test_resolve_accepts_prod_child_with_expected_version(self):
        result = self._resolve(PROD_BASE_AMD64)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"prod {PROD_BASE_AMD64} 8.4.22")

    def test_resolve_accepts_prod_index_and_normalises(self):
        result = self._resolve(PROD_BASE_INDEX)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"prod {PROD_BASE_AMD64} 8.4.22")

    def test_resolve_accepts_vm_child_with_expected_version(self):
        result = self._resolve(VM_BASE_AMD64)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"vm {VM_BASE_AMD64} 8.4.20")

    def test_resolve_accepts_vm_index_and_normalises(self):
        result = self._resolve(VM_BASE_INDEX)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"vm {VM_BASE_AMD64} 8.4.20")

    def test_resolve_rejects_mutable_and_unapproved_bases(self):
        for ref in (
            "invoiceninja/invoiceninja-debian:latest",
            "invoiceninja/invoiceninja-debian:8.4",
            "invoiceninja/invoiceninja-debian@sha256:deadbeef",
            "php:8.4-fpm",
            "invoiceninja/invoiceninja-octane:latest",
            "",
        ):
            with self.subTest(ref=ref):
                self.assertNotEqual(self._resolve(ref).returncode, 0, f"{ref!r} must be rejected")

    def test_manifest_changed_paths_extracts_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text(
                "D 0 0 755 /usr/local/bin\n"
                "F 0 0 755 /usr/local/bin/php\n"
                "H aaaa  /usr/local/bin/php\n"
                "H bbbb  /usr/local/bin/phpize\n"
            )
            cand.write_text(
                "D 0 0 755 /usr/local/bin\n"
                "F 0 0 755 /usr/local/bin/php\n"
                "H cccc  /usr/local/bin/php\n"
                "H bbbb  /usr/local/bin/phpize\n"
            )
            result = _bash(["-c", f'. "{COMMON}"; manifest_changed_paths "{base}" "{cand}"'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["/usr/local/bin/php"])

    def test_manifest_changed_paths_detects_metadata_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("F 0 0 755 /usr/local/bin/php\n")
            cand.write_text("F 1000 1000 644 /usr/local/bin/php\n")
            result = _bash(["-c", f'. "{COMMON}"; manifest_changed_paths "{base}" "{cand}"'])
            self.assertEqual(result.stdout.split(), ["/usr/local/bin/php"])

    def test_assert_metadata_unchanged_rejects_uid_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("F 0 0 755 /usr/local/bin/php\nH aaaa  /usr/local/bin/php\n")
            cand.write_text("F 1000 1000 755 /usr/local/bin/php\nH bbbb  /usr/local/bin/php\n")
            result = _bash(["-c", f'. "{COMMON}"; assert_metadata_unchanged "{base}" "{cand}" x'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("/usr/local/bin/php", result.stderr)

    def test_assert_metadata_unchanged_accepts_content_only_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("F 0 0 755 /usr/local/bin/php\nH aaaa  /usr/local/bin/php\n")
            cand.write_text("F 0 0 755 /usr/local/bin/php\nH bbbb  /usr/local/bin/php\n")
            result = _bash(["-c", f'. "{COMMON}"; assert_metadata_unchanged "{base}" "{cand}" x'])
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_assert_only_allowed_changes_accepts_exact_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("H aaaa  /usr/local/bin/php\n")
            cand.write_text("H bbbb  /usr/local/bin/php\n")
            result = _bash(["-c",
                            f'. "{COMMON}"; assert_only_allowed_changes "{base}" "{cand}" label /usr/local/bin/php'])
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_assert_only_allowed_changes_rejects_retained_module_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("H aaaa  /usr/local/bin/php\nH eeee  /usr/local/lib/php/extensions/x/imagick.so\n")
            cand.write_text("H bbbb  /usr/local/bin/php\nH ffff  /usr/local/lib/php/extensions/x/imagick.so\n")
            result = _bash(["-c",
                            f'. "{COMMON}"; assert_only_allowed_changes "{base}" "{cand}" label /usr/local/bin/php'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("imagick.so", result.stderr)

    def test_assert_no_changes_detects_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            base.write_text("H aaaa  /var/www/html/index.php\n")
            cand.write_text("H bbbb  /var/www/html/index.php\n")
            result = _bash(["-c", f'. "{COMMON}"; assert_no_changes "{base}" "{cand}" app'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("/var/www/html/index.php", result.stderr)

    def test_assert_no_changes_passes_when_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "base"
            cand = pathlib.Path(tmp) / "cand"
            text = "H aaaa  /var/www/html/index.php\n"
            base.write_text(text)
            cand.write_text(text)
            result = _bash(["-c", f'. "{COMMON}"; assert_no_changes "{base}" "{cand}" app'])
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_preflight_rejects_remote_docker_host(self):
        result = _bash(["-c", f'. "{COMMON}"; preflight_local_docker'],
                       env={**os.environ, "DOCKER_HOST": "ssh://root@runtime-host"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DOCKER_HOST", result.stderr)

    def test_preflight_fails_closed_on_empty_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, _ = _fake_docker_env(pathlib.Path(tmp), {"FAKE_CONTEXT_MODE": "empty"})
            result = _bash(["-c", f'. "{COMMON}"; preflight_local_docker'], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("empty", result.stderr)

    def test_preflight_fails_closed_on_context_inspection_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, _ = _fake_docker_env(pathlib.Path(tmp), {"FAKE_CONTEXT_MODE": "fail"})
            result = _bash(["-c", f'. "{COMMON}"; preflight_local_docker'], env=env)
            self.assertNotEqual(result.returncode, 0)

    def test_preflight_rejects_buildkit_host_override(self):
        result = _bash(["-c", f'. "{COMMON}"; preflight_local_docker'],
                       env={**os.environ, "BUILDKIT_HOST": "tcp://remote-builder:1234"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUILDKIT_HOST", result.stderr)

    def test_preflight_rejects_buildx_builder_override(self):
        result = _bash(["-c", f'. "{COMMON}"; preflight_local_docker'],
                       env={**os.environ, "BUILDX_BUILDER": "remote-builder"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUILDX_BUILDER", result.stderr)


# ---------------------------------------------------------------------------
# build-php.sh
# ---------------------------------------------------------------------------


class TestBuildScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(BUILD)

    def test_bash_syntax(self):
        self.assertEqual(_bash_n(BUILD).returncode, 0)

    def test_no_credentials_or_dotenv(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in (".env", "vault", "password", "secret", "token"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_no_host_network_or_ports(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in ("--network host", "--publish", "--privileged"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_never_pushes_or_prunes(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in ("push", "prune", "docker volume"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_uses_explicit_platform(self):
        self.assertIn('--platform "$BUILD_PLATFORM"', self.content)
        self.assertIn('BUILD_PLATFORM="linux/amd64"', _read(COMMON))

    def test_rejects_unapproved_base_without_calling_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            for ref in ("invoiceninja/invoiceninja-debian:latest",
                        "invoiceninja/invoiceninja-debian@sha256:deadbeef"):
                with self.subTest(ref=ref):
                    result = _bash([str(BUILD), "--base", ref], env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(_log_lines(log), [])
                    log.unlink(missing_ok=True)

    def test_rejects_excessive_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64, "--jobs", "99"], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--jobs must be <=", result.stderr)
            self.assertEqual(_log_lines(log), [])

    def test_rejects_remote_docker_host_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp),
                                        {"DOCKER_HOST": "ssh://root@runtime-host"})
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("build", _log_lines(log))

    def test_rejects_buildkit_host_override_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp),
                                        {"BUILDKIT_HOST": "tcp://remote-builder:1234"})
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BUILDKIT_HOST", result.stderr)
            self.assertEqual(_log_lines(log), [])

    def test_rejects_buildx_builder_override_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp),
                                        {"BUILDX_BUILDER": "remote-builder"})
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BUILDX_BUILDER", result.stderr)
            self.assertEqual(_log_lines(log), [])

    def test_approved_base_builds_with_pinned_child_platform_and_local_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            result = _bash([str(BUILD), "--base", PROD_BASE_INDEX], env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = _log_lines(log)
            build_calls = [ln for ln in lines if ln.startswith("build ")]
            self.assertEqual(len(build_calls), 1, lines)
            call = build_calls[0]
            self.assertIn("--platform linux/amd64", call)
            self.assertIn(f"--build-arg BASE_IMAGE={PROD_BASE_AMD64}", call)
            self.assertIn("--build-arg JOBS=2", call)
            self.assertIn("fk-cesis-invoiceninja-php-hotpatch:8.4.27-prod", call)
            self.assertNotIn("--network", call)
            self.assertNotIn(" -p ", call)
            self.assertNotIn(" -v ", call)
            self.assertFalse(any(ln.startswith("push") for ln in lines))

    def test_refuses_tag_that_names_a_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64, "--tag", "registry.example.com/x:y"], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_log_lines(log), [])

    def test_dry_run_does_not_invoke_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            result = _bash([str(BUILD), "--base", PROD_BASE_AMD64, "--dry-run"], env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(_log_lines(log), [])
            self.assertIn("docker build", result.stdout)
            self.assertIn("--platform linux/amd64", result.stdout)


# ---------------------------------------------------------------------------
# verify.sh
# ---------------------------------------------------------------------------


class TestVerifyScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(VERIFY)

    def test_bash_syntax(self):
        self.assertEqual(_bash_n(VERIFY).returncode, 0)

    def test_runtime_checks_use_no_network_platform_and_entrypoint(self):
        self.assertIn("--network none", self.content)
        self.assertIn("--entrypoint", self.content)
        self.assertIn('--platform "$BUILD_PLATFORM"', self.content)
        self.assertNotIn("--network host", self.content)

    def test_uses_ld_bind_now(self):
        self.assertIn("-e LD_BIND_NOW=1", self.content)

    def test_asserts_exact_versions(self):
        self.assertIn('^PHP 8\\.4\\.27 \\(cli\\) ', self.content)
        self.assertIn('^PHP 8\\.4\\.27 \\(fpm-fcgi\\) ', self.content)
        self.assertIn('= "3.8.1"', self.content)
        self.assertIn('= "12.5"', self.content)
        self.assertIn("candidate PHP_VERSION constant", self.content)

    def test_compares_static_and_full_module_sets(self):
        self.assertIn('run_php "$build_base" -n -m', self.content)
        self.assertIn('run_php "$CANDIDATE"  -n -m', self.content)

    def test_checks_metadata_and_features_and_symbols(self):
        self.assertIn("assert_metadata_unchanged", self.content)
        self.assertIn("feature_fingerprint", self.content)
        self.assertIn("container_symbol_check", self.content)

    def test_never_pulls_candidate(self):
        self.assertIn("refusing to pull it", self.content)
        self.assertIn('docker pull --platform "$BUILD_PLATFORM" "$build_base"', self.content)
        self.assertNotIn("docker pull \"$CANDIDATE\"", self.content)
        self.assertNotIn("docker pull '$CANDIDATE'", self.content)

    def test_never_runs_application_bootstrap(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in ("init.sh", "supervisord", "artisan", "migrate", "queue:work", "schedule:run"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_never_mounts_volumes_or_publishes_ports(self):
        for line in self.content.splitlines():
            if "docker run" not in line:
                continue
            for forbidden in (" -v ", " --volume", " -p ", " --publish", "--privileged"):
                with self.subTest(line=line, forbidden=forbidden):
                    self.assertNotIn(forbidden, line)

    def test_never_pushes_or_prunes(self):
        code = "\n".join(_code_lines(self.content))
        for forbidden in ("docker push", "prune", "docker volume"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_rejects_unapproved_base_without_calling_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp))
            result = _bash([str(VERIFY), "--base", "invoiceninja/invoiceninja-debian:latest"], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_log_lines(log), [])

    def test_rejects_remote_docker_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp), {"DOCKER_HOST": "tcp://runtime-host:2375"})
            result = _bash([str(VERIFY), "--base", VM_BASE_AMD64], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_log_lines(log), [])

    def test_missing_candidate_is_not_pulled(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, log = _fake_docker_env(pathlib.Path(tmp), {"FAKE_IMAGE_MISSING": "1"})
            result = _bash([str(VERIFY), "--base", PROD_BASE_AMD64], env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not present locally", result.stderr)
            pulls = [ln for ln in _log_lines(log) if ln.startswith("pull ")]
            self.assertTrue(all(PROD_BASE_AMD64 in ln for ln in pulls), pulls)
            self.assertFalse(any("fk-cesis-invoiceninja-php-hotpatch" in ln for ln in pulls), pulls)


# ---------------------------------------------------------------------------
# Directory hygiene
# ---------------------------------------------------------------------------


class TestHotpatchDirectory(unittest.TestCase):
    def test_expected_files_present(self):
        for name in ("Dockerfile", "common.sh", "build-php.sh", "verify.sh"):
            with self.subTest(name=name):
                self.assertTrue((HOTPATCH_DIR / name).is_file(), f"{name} missing")

    def test_scripts_are_executable(self):
        for name in ("build-php.sh", "verify.sh"):
            with self.subTest(name=name):
                self.assertTrue((HOTPATCH_DIR / name).stat().st_mode & stat.S_IXUSR, f"{name} not executable")

    def test_no_secret_material_committed(self):
        for path in HOTPATCH_DIR.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertNotIn(".env", path.name)
                    self.assertNotIn("vault", path.name)


if __name__ == "__main__":
    unittest.main()
