"""
Locust load test driving the real FastAPI app over HTTP (not the in-process
ASGI transport `tests/api`/`tests/performance` use) — this is the suite that
exercises actual network I/O, connection pooling under concurrency, and
uvicorn's request handling, not just business logic.

Requires a running API server and a seeded database. The e2e Playwright
suite already provides both prerequisites via `apps/api/scripts/seed_e2e.py`
(see `apps/web/e2e/global-setup.ts`), so this reuses that same seeded user
rather than seeding its own — run `python -m scripts.seed_e2e` from
`apps/api/` first if the target database doesn't already have it.

Usage (headless, 10 users, 30s, against a locally running API on :8000):

    locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000 \
        --headless --users 10 --spawn-rate 2 --run-time 30s

Or `locust -f tests/performance/locustfile.py` for the interactive web UI.
"""

import random

from locust import HttpUser, between, task

E2E_EMAIL = "e2e@erpx.example.com"
E2E_PASSWORD = "E2ePass123!"


class ErpxUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": E2E_EMAIL, "password": E2E_PASSWORD},
            name="/auth/login",
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(5)
    def list_leads(self) -> None:
        self.client.get("/api/v1/crm/leads?limit=20", name="/crm/leads [list]")

    @task(2)
    def create_lead(self) -> None:
        suffix = random.randint(0, 1_000_000)
        self.client.post(
            "/api/v1/crm/leads",
            json={
                "full_name": f"Load Test Lead {suffix}",
                "email": f"load.test.{suffix}@example.com",
                "source": "website",
            },
            name="/crm/leads [create]",
        )

    @task(3)
    def view_dashboard(self) -> None:
        self.client.get("/api/v1/dashboard/summary", name="/dashboard/summary")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/api/v1/health", name="/health")
