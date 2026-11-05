"""
The staging test gate (ops/staging-cashfree/gateway.conf + gate-templates/), run against a REAL nginx with stub upstreams.

`./staging.sh gate on` copies the templates into the folder the staging gateway includes. With the gate on:
- Cashfree's webhook endpoint answers 503 (the webhook is "lost"),
- the checkout return page (/internship-onboarding?order=...) is answered by the gateway, so the web app never loads
  there and never sends its automatic status check,
- everything else, including the API's POST .../payments/refresh that the "I have paid: check status" button calls,
  still reaches its upstream.
With the gate off (the folder empty) nothing is changed. Staging gateway only: the API and the web app are untouched.
`./staging.sh recon on` (the scheduled-reconciliation test) installs the same two plus a third template that also refuses the
student's status-check endpoint (POST .../payments/refresh) with 503, so no student-side check can reach ERPX; checkout and
the rest of the API stay open. Skipped when no nginx binary is installed.
"""

import http.client
import os
import shutil
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

KIT = Path(__file__).resolve().parents[2] / "ops" / "staging-cashfree"
NGINX = shutil.which("nginx") or ("/usr/sbin/nginx" if Path("/usr/sbin/nginx").exists() else None)
WEBHOOK = "/api/v1/public/payments/cashfree/webhook"
REFRESH = "/api/v1/public/internship-onboarding/payments/refresh"
CHECKOUT = "/api/v1/public/internship-onboarding/payments/checkout"

pytestmark = [pytest.mark.unit, pytest.mark.skipif(NGINX is None, reason="needs an nginx binary")]


class Upstream:
    """A stub upstream that remembers every request it receives."""

    def __init__(self, name: str):
        self.name, self.seen = name, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                outer.seen.append(f"{self.command} {self.path}")
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                body = f"from {outer.name}".encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _answer

            def log_message(self, *args):  # silence
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Gateway:
    def __init__(self, tmp: Path):
        self.api, self.web, self.storage = Upstream("api"), Upstream("web"), Upstream("storage")
        self.port = free_port()
        self.gate = tmp / "gate"
        self.gate.mkdir()
        conf = (KIT / "gateway.conf").read_text()
        for old, new in (
            ("server api:8000;", f"server 127.0.0.1:{self.api.port};"),
            ("server web:80;", f"server 127.0.0.1:{self.web.port};"),
            ("server minio:9000;", f"server 127.0.0.1:{self.storage.port};"),
            ("listen 80;", f"listen 127.0.0.1:{self.port};"),
            ("/etc/nginx/staging-gate", str(self.gate)),
        ):
            assert old in conf, old
            conf = conf.replace(old, new)
        (tmp / "gateway.conf").write_text(conf)
        (tmp / "temp").mkdir()
        (tmp / "nginx.conf").write_text(
            ("user root;\n" if os.geteuid() == 0 else "")
            + f"daemon off;\nworker_processes 1;\npid {tmp}/nginx.pid;\nerror_log {tmp}/error.log;\nevents {{}}\n"
            + f"http {{\n access_log off;\n client_body_temp_path {tmp}/temp/body;\n proxy_temp_path {tmp}/temp/proxy;\n"
            + f" include {tmp}/gateway.conf;\n}}\n"
        )
        self.tmp = tmp
        self.cmd = [NGINX, "-p", str(tmp), "-c", str(tmp / "nginx.conf")]

    def test_config(self) -> subprocess.CompletedProcess:
        return subprocess.run([*self.cmd, "-t"], capture_output=True, text=True)

    def start(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(50):
            try:
                self.request("GET", "/__ready")
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("nginx did not start: " + (self.tmp / "error.log").read_text())

    def reload(self):
        os.kill(int((self.tmp / "nginx.pid").read_text()), signal.SIGHUP)
        time.sleep(0.5)

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)

    def request(self, method: str, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=b"{}" if method == "POST" else None)
        response = conn.getresponse()
        body = response.read().decode()
        conn.close()
        return response.status, body

    def gate_on(self, mode: str = "manual"):
        templates = list((KIT / "gate-templates").glob("*.conf"))
        if mode == "reconcile":  # ./staging.sh recon on: the same two, plus the refusal of the student's status-check endpoint
            templates += list((KIT / "gate-templates" / "reconcile").glob("*.conf"))
        for template in templates:
            shutil.copy(template, self.gate / template.name)
        assert self.test_config().returncode == 0
        self.reload()

    def gate_off(self):
        for f in self.gate.glob("*.conf"):
            f.unlink()
        self.reload()

    def clear(self):
        for upstream in (self.api, self.web, self.storage):
            upstream.seen.clear()


@pytest.fixture
def gateway(tmp_path):
    gw = Gateway(tmp_path)
    assert gw.test_config().returncode == 0, gw.test_config().stderr  # an empty gate folder is a valid configuration
    gw.start()
    yield gw
    gw.stop()


def test_with_the_gate_off_the_gateway_behaves_as_before(gateway):
    assert gateway.request("POST", WEBHOOK) == (200, "from api")
    assert gateway.request("GET", "/internship-onboarding?order=ERPXI123") == (200, "from web")
    assert gateway.request("POST", REFRESH) == (200, "from api")
    assert [s for s in gateway.api.seen if "cashfree/webhook" in s] and any("order=ERPXI123" in s for s in gateway.web.seen)


def test_with_the_gate_on_the_webhook_is_refused_and_the_return_page_never_reaches_the_web_app(gateway):
    gateway.gate_on()
    gateway.clear()

    status, _ = gateway.request("POST", WEBHOOK)
    assert status == 503 and gateway.api.seen == []  # the notification never reaches ERPX

    status, body = gateway.request("GET", "/internship-onboarding?order=ERPXI123")
    assert status == 200 and "Staging test gate is on" in body
    assert gateway.request("GET", "/internship-onboarding/?order=ERPXI123")[1].count("Staging test gate is on") == 1
    assert gateway.web.seen == []  # the web app never loaded, so it cannot send its automatic status check
    assert gateway.api.seen == []


def test_with_the_gate_on_the_button_path_and_everything_else_stay_open(gateway):
    gateway.gate_on()
    gateway.clear()

    # the student's page without ?order= loads normally; this is where the button is
    assert gateway.request("GET", "/internship-onboarding") == (200, "from web")
    assert gateway.request("GET", "/internship-onboarding#token=abc") == (200, "from web")
    # the endpoint the button calls reaches the API, and so do other API calls
    assert gateway.request("POST", REFRESH) == (200, "from api")
    assert gateway.request("GET", "/api/v1/health") == (200, "from api")
    # only the return page is gated: other pages and assets that happen to carry an order parameter are not
    assert gateway.request("GET", "/assets/app.js?order=1") == (200, "from web")
    assert gateway.request("GET", "/internship-onboarding/other?order=1") == (200, "from web")
    assert gateway.api.seen == [f"POST {REFRESH}", "GET /api/v1/health"]


def test_switching_the_gate_off_restores_both_paths(gateway):
    gateway.gate_on()
    assert gateway.request("POST", WEBHOOK)[0] == 503
    gateway.gate_off()
    gateway.clear()
    assert gateway.request("POST", WEBHOOK) == (200, "from api")
    assert gateway.request("GET", "/internship-onboarding?order=ERPXI123") == (200, "from web")
    assert gateway.api.seen and gateway.web.seen


def test_recon_mode_also_refuses_the_students_status_check_but_nothing_else(gateway):
    gateway.gate_on("reconcile")
    gateway.clear()

    # the three things that could confirm a payment before the scheduled task: all out of the way
    assert gateway.request("POST", WEBHOOK)[0] == 503
    status, body = gateway.request("GET", "/internship-onboarding?order=ERPXI123")
    assert status == 200 and "Staging test gate is on" in body
    assert gateway.request("POST", REFRESH)[0] == 503
    assert gateway.api.seen == [] and gateway.web.seen == []  # none of them reached ERPX

    # ...while the student can still open the page, start a checkout and use the rest of the API
    assert gateway.request("GET", "/internship-onboarding") == (200, "from web")
    assert gateway.request("POST", CHECKOUT) == (200, "from api")
    assert gateway.request("GET", "/api/v1/health") == (200, "from api")
    assert gateway.api.seen == [f"POST {CHECKOUT}", "GET /api/v1/health"]


def test_manual_mode_keeps_the_status_check_open_and_recon_mode_off_restores_it(gateway):
    gateway.gate_on("manual")
    assert gateway.request("POST", REFRESH) == (200, "from api")  # the button's endpoint is open in the button test
    gateway.gate_off()
    gateway.gate_on("reconcile")
    assert gateway.request("POST", REFRESH)[0] == 503
    gateway.gate_off()
    gateway.clear()
    assert gateway.request("POST", REFRESH) == (200, "from api")
    assert gateway.request("POST", WEBHOOK) == (200, "from api")
    assert gateway.request("GET", "/internship-onboarding?order=ERPXI123") == (200, "from web")
