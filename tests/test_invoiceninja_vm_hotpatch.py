#!/usr/bin/env python3
"""Contract tests for selecting the PHP-hotpatch image in Compose.

These tests are hermetic: they render the Compose Jinja2 template with a small
keyword-only renderer, never contact Docker, and never read credentials or the
vault. They prove:

* the role default remains the original upstream reference, used only when an
  inventory does not override it;
* the local VM inventory selects the VM-native OCI image ID verified on the
  Docker 29 host;
* the production inventory selects its own production-native OCI image ID;
* the two inventories never mix native image IDs with the accepted source
  config digests;
* the disposable smoke script keeps its isolation guardrails and still defaults
  to the accepted local candidate (classic Docker config digest), which is not
  the VM inventory pin.

Identity provenance, verified cryptographically without archives. The local VM
accepted source config digest is 6892... and the smoke default, while Docker 29
reports the imported OCI manifest/image ID 9248...; the VM containerd ``moby``
namespace manifest bytes hash to 9248, its config descriptor is 6892, the
22,261-byte config blob hashes to 6892, and the 26 ordered layer descriptors
match the source ``diff_ids`` exactly. Production was transferred the same way:
the accepted source config digest is 14c1..., while Docker 29 reports the
production-native manifest/image ID b8e3...; its config descriptor is 14c1,
the actual 22,654-byte config blob hashes to 14c1, and all 26 uncompressed tar
descriptors match the source ordered ``RootFS.diffIDs`` for linux/amd64. The
inventories pin the native image IDs (9248 VM, b8e3 production), never the
source config digests.

Uses only the Python standard library.
"""

import pathlib
import re
import stat
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULTS = REPO_ROOT / "ansible/roles/football_club_stack/defaults/main.yml"
COMPOSE = REPO_ROOT / "ansible/roles/football_club_stack/templates/docker-compose.yml.j2"
VM_VARS = REPO_ROOT / "ansible/inventories/local_vm/group_vars/local_vm/vars.yml"
PROD_VARS = REPO_ROOT / "ansible/inventories/production/group_vars/production/vars.yml"
SMOKE = REPO_ROOT / "docker/invoiceninja-php-hotpatch/smoke-local.sh"

VAR = "football_club_stack_invoiceninja_image"
UPSTREAM = "invoiceninja/invoiceninja-debian:latest"
VM_IMAGE_ID = (
    "sha256:9248d42e08d5cfbbdb7da7ffb0b8ac9e925df511bd5a625770566c329c6b928f"
)
# Local accepted source image: Docker classic config digest, also the smoke
# default. It is NOT the Docker 29 VM image ID; the manifest config descriptor
# links the two.
LOCAL_CANDIDATE_ID = (
    "sha256:68921270adf885a6fcedee6fde24851be517dd6d6b5579df731b688516c7d248"
)
PROD_IMAGE_ID = (
    "sha256:b8e368e6fa68c2a715d0100455f06e17827d4652398c63e2fcaed092f2b0632e"
)
# Accepted local source for the production image: config descriptor/blob digest,
# not the Docker 29 production-native image ID the inventory pins.
LOCAL_PROD_SOURCE_ID = (
    "sha256:14c1af817177f9c81bbeef6a5b3964ed478b5462776b9ed909c6115f1b72b2b6"
)
SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def _read(path: pathlib.Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing required file: {path}")
    return path.read_text()


def _scalar_map(text: str) -> dict:
    """Return top-level `key: scalar` pairs; folded blocks become empty strings."""
    values = {}
    for line in text.splitlines():
        match = re.match(r"^([a-z][a-z0-9_]*):\s*(.*?)\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        if value in (">-", ">", "|", "|-"):
            value = ""
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _render(template: str, values: dict) -> str:
    """Render the simple `{{ variable }}` expressions used by this template."""
    pattern = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")

    def replace(match):
        key = match.group(1)
        if key not in values:
            raise AssertionError(f"unresolved template variable: {key}")
        return values[key]

    rendered = pattern.sub(replace, template)
    if "{{" in rendered or "{%" in rendered:
        raise AssertionError("template uses Jinja2 syntax this test renderer does not support")
    return rendered


def _invoiceninja_block(rendered: str) -> str:
    match = re.search(
        r"^  invoiceninja:\s*$\n((?:(?:    .*)?\n)+?)(?=^  \S|\Z)",
        rendered,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError("could not extract invoiceninja service block")
    return match.group(1)


def _invoiceninja_image(rendered: str) -> str:
    block = _invoiceninja_block(rendered)
    match = re.search(r"^\s+image:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", block, re.MULTILINE)
    if not match:
        raise AssertionError("invoiceninja service has no image line")
    return match.group(1)


def _code_lines(content: str):
    """Return non-comment, non-blank shell lines (prose may mention forbidden terms)."""
    return [
        line
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class TestImageSelection(unittest.TestCase):
    def setUp(self):
        self.defaults_text = _read(DEFAULTS)
        self.compose_text = _read(COMPOSE)
        self.vm_text = _read(VM_VARS)
        self.prod_text = _read(PROD_VARS)
        self.defaults = _scalar_map(self.defaults_text)
        self.vm = _scalar_map(self.vm_text)
        self.prod = _scalar_map(self.prod_text)

    def test_default_image_is_original_upstream_reference(self):
        self.assertEqual(self.defaults.get(VAR), UPSTREAM)

    def test_vm_image_is_the_verified_vm_native_full_sha256_id(self):
        self.assertTrue(SHA256_ID.match(self.vm.get(VAR, "")), self.vm.get(VAR))
        self.assertEqual(self.vm.get(VAR), VM_IMAGE_ID)
        self.assertNotEqual(self.vm.get(VAR), LOCAL_CANDIDATE_ID)

    def test_production_inventory_pins_the_verified_native_image(self):
        self.assertTrue(SHA256_ID.match(self.prod.get(VAR, "")), self.prod.get(VAR))
        self.assertEqual(self.prod.get(VAR), PROD_IMAGE_ID)
        self.assertNotEqual(self.prod.get(VAR), LOCAL_PROD_SOURCE_ID)
        self.assertNotEqual(self.prod.get(VAR), VM_IMAGE_ID)

    def test_inventories_do_not_mix_source_config_digests_with_native_image_ids(self):
        for digest in (LOCAL_CANDIDATE_ID, LOCAL_PROD_SOURCE_ID, VM_IMAGE_ID):
            with self.subTest(inventory="production", digest=digest):
                self.assertNotIn(digest, self.prod_text)
        for digest in (PROD_IMAGE_ID, LOCAL_CANDIDATE_ID, LOCAL_PROD_SOURCE_ID):
            with self.subTest(inventory="local_vm", digest=digest):
                self.assertNotIn(digest, self.vm_text)

    def test_compose_uses_the_image_variable(self):
        self.assertIn(f'image: "{{{{ {VAR} }}}}"', self.compose_text)
        self.assertNotIn("image: invoiceninja/invoiceninja-debian:latest", self.compose_text)

    def test_fallback_default_is_used_without_an_inventory_override(self):
        rendered = _render(self.compose_text, dict(self.defaults))
        self.assertEqual(_invoiceninja_image(rendered), UPSTREAM)

    def test_vm_render_selects_the_verified_vm_native_image(self):
        rendered = _render(self.compose_text, {**self.defaults, **self.vm})
        self.assertEqual(_invoiceninja_image(rendered), VM_IMAGE_ID)

    def test_production_render_selects_the_verified_production_native_image(self):
        rendered = _render(self.compose_text, {**self.defaults, **self.prod})
        self.assertEqual(_invoiceninja_image(rendered), PROD_IMAGE_ID)

    def test_vm_and_production_render_different_images(self):
        vm_render = _render(self.compose_text, {**self.defaults, **self.vm})
        prod_render = _render(self.compose_text, {**self.defaults, **self.prod})
        vm_image = _invoiceninja_image(vm_render)
        prod_image = _invoiceninja_image(prod_render)
        self.assertNotEqual(vm_image, prod_image)
        self.assertEqual(vm_image, VM_IMAGE_ID)
        self.assertEqual(prod_image, PROD_IMAGE_ID)


class TestDisposableSmokeScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = _read(SMOKE)
        cls.code = "\n".join(_code_lines(cls.content))

    def test_bash_syntax(self):
        result = subprocess.run(["bash", "-n", str(SMOKE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_is_executable(self):
        self.assertTrue(SMOKE.stat().st_mode & stat.S_IXUSR)

    def test_defaults_to_the_local_candidate_not_the_vm_image_id(self):
        self.assertIn(LOCAL_CANDIDATE_ID, self.content)
        self.assertNotIn(VM_IMAGE_ID, self.content)

    def test_uses_only_local_images_and_never_pulls_or_pushes(self):
        for forbidden in ("docker pull", "docker push", "docker image pull"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)

    def test_isolates_network_and_publishes_no_ports(self):
        self.assertIn("--internal", self.code)
        self.assertIn("--network none", self.code)
        for line in self.code.splitlines():
            if "docker run" not in line:
                continue
            for forbidden in ("--network host", " --publish", " -p ", "--privileged"):
                with self.subTest(forbidden=forbidden, line=line):
                    self.assertNotIn(forbidden, line)

    def test_never_runs_the_normal_entrypoint_or_supervisord(self):
        self.assertIn("--entrypoint", self.code)
        for forbidden in ("init.sh", "supervisord -c"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)

    def test_heredoc_fed_docker_runs_are_interactive(self):
        """Without -i the heredoc is not attached and the PHP gate can be skipped."""
        fed = 0
        for line in self.code.splitlines():
            if "docker run" in line and "<<" in line:
                fed += 1
                with self.subTest(line=line):
                    self.assertRegex(line, r"(?:^|\s)(?:-i|--interactive)(?:\s|$)")
        self.assertGreaterEqual(fed, 2)

    def test_cleanup_removes_anonymous_volumes(self):
        """MariaDB's /var/lib/mysql is an anonymous volume; -v is mandatory."""
        self.assertIn('docker rm -fv "$APP" "$DB"', self.code)
        self.assertNotIn('docker rm -f "$APP" "$DB"', self.code)

    def test_cleanup_is_scoped_and_never_prunes(self):
        self.assertIn("trap cleanup", self.code)
        self.assertIn("docker network rm", self.code)
        self.assertIn("docker volume rm", self.code)
        self.assertNotIn("prune", self.code)


if __name__ == "__main__":
    unittest.main()
