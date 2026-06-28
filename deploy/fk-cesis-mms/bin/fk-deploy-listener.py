#!/usr/bin/env python3
"""Tiny HMAC-verified deploy webhook for fk-cesis-mms.

Listens on DEPLOY_LISTENER_HOST:DEPLOY_LISTENER_PORT (defaults to
127.0.0.1:9000; loopback only — Caddy proxies the public route).
POST /hooks/codeberg with X-FK-Signature: sha256=<hmac-sha256(body, SECRET)>
runs /opt/fk-cesis-mms/bin/deploy-fk-cesis-mms.sh and returns 202.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ["DEPLOY_WEBHOOK_SECRET"].encode()
DEPLOY_CMD = ["/opt/fk-cesis-mms/bin/deploy-fk-cesis-mms.sh"]
LISTEN_HOST = os.environ.get("DEPLOY_LISTENER_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("DEPLOY_LISTENER_PORT", "9000"))


def _pipe_to_journald(proc: subprocess.Popen) -> None:
    """Forward the deploy script's combined stdout/stderr into journald.

    Without this the Popen would drop output, hiding any failure that
    happens after the listener has already sent 202 back to CI.
    """
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"[deploy] {line.rstrip()}", flush=True)
    proc.wait()
    print(f"[deploy] script exited rc={proc.returncode}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/hooks/codeberg":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        sig_header = self.headers.get("X-FK-Signature", "")
        if not sig_header.startswith("sha256="):
            self._reject("missing signature")
            return
        expected = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig_header.removeprefix("sha256=")):
            self._reject("bad signature")
            return
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"accepted\n")
        # Run the deploy script in the background, capture both streams,
        # and pipe each line back to our own stdout so it lands in journald
        # (alongside the listener's access log). Without this, any failure
        # inside the script is invisible because Popen would otherwise drop
        # the streams.
        proc = subprocess.Popen(
            DEPLOY_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
            bufsize=1,
        )
        threading.Thread(
            target=_pipe_to_journald,
            args=(proc,),
            daemon=True,
        ).start()

    def _reject(self, reason: str) -> None:
        self.send_response(401)
        self.end_headers()
        self.wfile.write(reason.encode() + b"\n")

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[fk-deploy] {self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
