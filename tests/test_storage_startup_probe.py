from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


class ProbePrimary:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def ping(self):
        self.calls += 1
        if self.fail:
            raise TimeoutError("probe down")
        return True

    def close(self):
        return None


class LifespanProbeStore:
    def __init__(self):
        self.probes = 0
        self.closed = 0

    def probe_primary(self):
        self.probes += 1
        return True

    def close(self):
        self.closed += 1


def test_supabase_ping_is_read_only_head():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = request.url.query.decode() if isinstance(request.url.query, bytes) else str(request.url.query)
        seen["probe"] = request.headers.get("x-bco-storage-probe")
        seen["body"] = request.content
        return httpx.Response(200, headers={"content-range": "0-0/0"})

    store = SupabaseStore(url="https://example.supabase.co", service_role_key="secret")
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    try:
        assert store.ping() is True
    finally:
        store.close()

    assert seen["method"] == "HEAD"
    assert seen["path"].endswith("/rest/v1/bco_players")
    assert "select=chat_id" in seen["query"]
    assert seen["probe"] == "startup-v39"
    assert seen["body"] in (b"", None)


def test_resilient_probe_success_updates_readiness_state():
    primary = ProbePrimary(fail=False)
    store = ResilientStore(primary, InMemoryStore())
    assert store.probe_primary() is True
    status = store.recovery_status()
    assert primary.calls == 1
    assert status["primary_available"] is True
    assert status["last_probe_ok"] is True
    assert status["probe_successes"] == 1
    assert status["probe_failures"] == 0
    assert status["last_primary_error"] == ""
    assert status["last_probe_at"]


def test_resilient_probe_failure_is_visible_without_crashing():
    primary = ProbePrimary(fail=True)
    store = ResilientStore(primary, InMemoryStore())
    assert store.probe_primary() is False
    status = store.recovery_status()
    assert status["primary_available"] is False
    assert status["last_probe_ok"] is False
    assert status["probe_successes"] == 0
    assert status["probe_failures"] == 1
    assert status["last_primary_error"] == "TimeoutError"


def test_fastapi_lifespan_runs_storage_probe(monkeypatch):
    import app.webhook as webhook

    fake = LifespanProbeStore()
    monkeypatch.setattr(webhook, "build_store", lambda _settings: fake)
    app = webhook.create_app()

    with TestClient(app) as client:
        assert fake.probes == 1
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    assert fake.closed == 1
