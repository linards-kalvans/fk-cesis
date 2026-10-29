#!/usr/bin/env python3
"""Opt-in local Caddy/nginx/accepted-PHP forwarding integration test.

Never pulls images or touches the deployed stack. Requires Linux, a local Docker
daemon, OpenSSL, and preloaded immutable fixture images. Resources have unique
names; cleanup removes only those resources, including anonymous image volumes.
The real Caddy binary runs unprivileged with a synthetic TLS cert on loopback.
"""

import argparse
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid

import yaml

from test_deployment_security import ROOT, ROLE, render_stack


NGINX = "nginx@sha256:2db7d28517d1fba17c2da3210395f7be11a11b419246ad0da2edf782af72f367"
CADDY = "caddy@sha256:04913b1da43339a40ad1ea87827d70a576ac5aa6cf674c6e24fdca675887533a"
FIXTURES = ROOT / "tests/fixtures/proxy"


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"docker {args[0]} failed: {result.stderr}")
    return result.stdout.strip()


def get(port, headers, tls=False, path="/api/v1/clients?test=1"):
    connection = (http.client.HTTPSConnection(
        "127.0.0.1", port, timeout=2, context=ssl._create_unverified_context()
    ) if tls else http.client.HTTPConnection("127.0.0.1", port, timeout=2))
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read().decode()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {body[:300]}")
        return json.loads(body)
    finally:
        connection.close()


def wait_ready(callback, process=None):
    deadline = time.monotonic() + 20
    while True:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Caddy exited before becoming ready")
        try:
            return callback()
        except (OSError, ValueError, http.client.HTTPException, RuntimeError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-image", required=True, help="preloaded accepted local image ID")
    parser.add_argument("--nginx-image", default=NGINX, help="preloaded immutable nginx reference")
    parser.add_argument("--caddy-binary", type=Path, help="existing native Caddy instead of extracting the fixture")
    parser.add_argument("--inventory", choices=("production", "local_vm"), default="production")
    parser.add_argument("--expect-vulnerable", action="store_true", help="baseline reproduction only")
    args = parser.parse_args()
    if sys.platform != "linux" or not __debug__:
        parser.error("requires Linux and Python without assertion-disabling optimization")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.app_image):
        parser.error("--app-image must be a full sha256 image ID, not a mutable tag")
    if not re.fullmatch(r"(?:[a-zA-Z0-9./:_-]+@)?sha256:[0-9a-f]{64}", args.nginx_image):
        parser.error("--nginx-image must be an immutable image reference")
    if args.caddy_binary is not None and not (args.caddy_binary.is_file() and os.access(args.caddy_binary, os.X_OK)):
        parser.error("--caddy-binary must be an existing executable")
    # Guard against inadvertently targeting production via a remote Docker context.
    context = json.loads(docker("context", "inspect"))[0]
    endpoint = context["Endpoints"]["docker"]["Host"]
    if not endpoint.startswith("unix://") or not os.environ.get("DOCKER_HOST", endpoint).startswith("unix://"):
        parser.error("only a local Unix-socket Docker daemon is permitted")
    for image in (args.app_image, args.nginx_image, *((CADDY,) if args.caddy_binary is None else ())):
        docker("image", "inspect", image)

    name = "fk-proxy-smoke-" + uuid.uuid4().hex[:12]
    app, nginx, client, fixture = [name + suffix for suffix in ("-app", "-nginx", "-client", "-fixture")]
    process = None
    with tempfile.TemporaryDirectory(prefix=name + "-") as directory:
        work = Path(directory)
        work.chmod(0o755)
        config = work / "nginx"
        config.mkdir()
        public = work / "public"
        public.mkdir()
        (public / "index.php").write_text((FIXTURES / "index.php").read_text())
        for source in (ROLE / "templates").iterdir():
            if source.name in ("invoiceninja.conf", "laravel.conf", "start-nginx.sh"):
                (config / source.name).write_text(source.read_text())
        caddy_log = work / "caddy.log"
        try:
            docker("network", "create", name)
            trust = yaml.safe_load(render_stack(args.inventory))["services"]["invoiceninja"]["environment"]["TRUSTED_PROXIES"]
            docker("run", "-d", "--name", app, "--pull", "never", "--network", name,
                   "--network-alias", "invoiceninja", "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--user", "33:33",
                   "-e", f"TRUSTED_PROXIES={trust}",
                   "-v", f"{public}:/var/www/html/public:ro",
                   "-v", f"{FIXTURES / 'fpm.conf'}:/tmp/proxy-fpm.conf:ro",
                   "--entrypoint", "php-fpm", args.app_image, "-n", "-F", "-y", "/tmp/proxy-fpm.conf")
            command = yaml.safe_load(render_stack(args.inventory))["services"]["nginx"]["command"]
            command = shlex.split(command) if isinstance(command, str) else command
            docker("run", "-d", "--name", nginx, "--pull", "never", "--network", name,
                   "--network-alias", "nginx", "-p", "127.0.0.1::80",
                   "-v", f"{config}:/etc/nginx/conf.d:ro",
                   "-v", f"{public}:/var/www/html/public:ro", args.nginx_image, *command)
            port = int(docker("port", nginx, "80/tcp").rsplit(":", 1)[1])
            base_headers = {"Host": "billing.example.test", "Authorization": "Bearer synthetic",
                            "X-API-Token": "synthetic", "Cookie": "proxy_smoke=present"}
            wait_ready(lambda: get(port, base_headers))

            # A normal container peer on the same network (the MMS route), not
            # the host/gateway. PHP's standard-library HTTP wrapper is sufficient.
            attack = {**base_headers, "X-Forwarded-For": "203.0.113.66",
                      "X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "https",
                      "X-Forwarded-Port": "444", "X-Forwarded-Prefix": "/evil",
                      "X-Forwarded-Ssl": "on", "X-Forwarded-Server": "attacker.example",
                      "Forwarded": "for=203.0.113.67;host=attacker.example;proto=https"}
            php = ('$context=stream_context_create(["http"=>["header"=>' +
                   json.dumps("\r\n".join(f"{key}: {value}" for key, value in {**attack, "Host": "nginx"}.items())) +
                   ']]); echo json_encode(["source_ip"=>gethostbyname(gethostname()),"response"=>'
                   'json_decode(file_get_contents("http://nginx/api/v1/clients?test=1",false,$context),true)]);')
            internal_result = json.loads(docker("run", "--rm", "--name", client, "--pull", "never",
                                         "--network", name, "--read-only", "--cap-drop", "ALL",
                                         "--security-opt", "no-new-privileges", "--entrypoint", "php",
                                         args.app_image, "-n", "-r", php))
            internal = internal_result["response"]
            if args.expect_vulnerable:
                assert internal["ip"] == "203.0.113.66", internal
                assert internal["host"] == "attacker.example", internal
                assert internal["scheme"] == "https", internal
                print("REPRODUCED: internal peer controls forwarded IP, host, HTTPS scheme and port")
                return
            assert internal["ip"] == internal_result["source_ip"], internal
            assert (internal["scheme"], internal["host"], internal["port"]) == ("http", "nginx", 80), internal
            assert not internal["forwarded"], internal

            # Extract the static official Caddy binary instead of granting a
            # container host networking. No trust-store or system config changes.
            caddy_binary = args.caddy_binary.resolve() if args.caddy_binary is not None else work / "caddy"
            if args.caddy_binary is None:
                docker("create", "--name", fixture, "--pull", "never", CADDY)
                docker("cp", f"{fixture}:/usr/bin/caddy", str(caddy_binary))
                docker("rm", "-v", fixture)
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(work / "key.pem"), "-out", str(work / "cert.pem"),
                            "-subj", "/CN=localhost", "-days", "1"],
                           check=True, capture_output=True)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                tls_port = listener.getsockname()[1]
            caddyfile = work / "Caddyfile"
            caddyfile.write_text(
                "{\n admin off\n auto_https off\n}\n" +
                f"https://:{tls_port} {{\n bind 127.0.0.1\n" +
                f" tls {work}/cert.pem {work}/key.pem\n reverse_proxy 127.0.0.1:{port}\n}}\n"
            )
            with caddy_log.open("w") as log:
                process = subprocess.Popen([str(caddy_binary), "run", "--config", str(caddyfile),
                                            "--adapter", "caddyfile"], stdout=log, stderr=log,
                                           env={**os.environ, "HOME": str(work),
                                                "XDG_DATA_HOME": str(work / "data"),
                                                "XDG_CONFIG_HOME": str(work / "config")})
                external = wait_ready(lambda: get(tls_port, {**attack, "X-Forwarded-Proto": "http"}, tls=True), process)
                assert (external["ip"], external["scheme"], external["host"], external["port"]) == (
                    "127.0.0.1", "https", "billing.example.test", 443
                ), external
                assert external["url"] == "https://billing.example.test/api/v1/clients", external
                assert not external["forwarded"], external
                for response in (external, internal):
                    assert response["authorization"] == "Bearer synthetic", response
                    assert response["api_token"] == "synthetic", response
                    assert response["cookie"] == "present", response
                    assert response["path"] == "api/v1/clients", response
                print("PASS: public Caddy TLS spoofing rejected; HTTPS URL, client IP and port preserved")
                print("PASS: internal MMS-style HTTP spoofing rejected; path, auth headers and cookie preserved")
                print("Caddy:", subprocess.run([str(caddy_binary), "version"], text=True,
                                               capture_output=True, check=True).stdout.strip())
                print("PHP image:", args.app_image)
        except Exception:
            for container in (app, nginx):
                print(docker("logs", container, check=False))
            if caddy_log.exists():
                print(caddy_log.read_text())
            raise
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            docker("rm", "-fv", client, nginx, app, fixture, check=False)
            docker("network", "rm", name, check=False)
            remaining = docker("ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}")
            remaining_network = docker("network", "ls", "--filter", f"name={name}", "--format", "{{.Name}}")
            if remaining or remaining_network:
                raise RuntimeError(f"Smoke cleanup incomplete: {remaining} {remaining_network}")


if __name__ == "__main__":
    main()
