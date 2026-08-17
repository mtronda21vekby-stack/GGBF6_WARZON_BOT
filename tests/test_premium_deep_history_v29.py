from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.operator_intelligence.deep_history import PremiumDeepHistoryService
from app.services.storage.memory import InMemoryStore
from app.webapp import command_center_router as cc


def _mission(store: InMemoryStore, idx: int, outcome: str, focus: str = "rotations") -> None:
    store.add_progression_event(77, {
        "type": "operator_mission",
        "status": "completed",
        "mission_id": f"m{idx}",
        "focus": focus,
        "outcome": outcome,
        "at": f"2026-08-{(idx % 28) + 1:02d}T00:00:{idx % 60:02d}+00:00",
    })


class Profiles:
    def get(self, chat_id):
        return {}

    def patch(self, chat_id, patch):
        return None


class Entitlements:
    def __init__(self, *, premium: bool, fail: bool = False, include_key: bool = True):
        self.premium = premium
        self.fail = fail
        self.include_key = include_key
        self.calls = []

    async def get_status(self, user_id: int):
        self.calls.append(user_id)
        if self.fail:
            raise RuntimeError("authority_down")
        entitlements = ("bco_premium",) if self.include_key else ()
        return SimpleNamespace(premium=self.premium, entitlements=entitlements)


def _client(monkeypatch, store, entitlements):
    monkeypatch.setattr(cc, "verify_init_data", lambda raw: (True, {"chat_id": 77, "user_id": 991}))
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=entitlements)
    app = FastAPI()
    app.include_router(cc.router)
    return TestClient(app)


def test_deep_history_uses_longer_bounded_horizon_without_causal_claims():
    store = InMemoryStore()
    outcomes = ["failed", "mixed", "clean", "clean", "mixed", "clean"]
    for idx in range(50):
        _mission(store, idx, outcomes[idx % len(outcomes)])

    data = PremiumDeepHistoryService(store).snapshot(77)
    assert data["schema"] == "bco_premium_deep_history_v29"
    assert data["horizon"]["max_cycles"] == 36
    assert data["horizon"]["observed_cycles"] <= 36
    assert data["truth_contract"]["association_not_causation"] is True
    assert data["truth_contract"]["causal_claims"] is False
    assert data["truth_contract"]["client_premium_authority"] is False
    assert len(data["timeline"]) <= 12


def test_nonpremium_and_link_only_users_are_denied(monkeypatch):
    store = InMemoryStore()
    entitlements = Entitlements(premium=False, include_key=True)
    client = _client(monkeypatch, store, entitlements)
    response = client.get("/webapp/api/operator-deep-history", headers={"X-Telegram-Init-Data": "signed"})
    assert response.status_code == 403
    assert response.json()["detail"] == "bco_premium_required"
    assert entitlements.calls == [991]

    link_only = Entitlements(premium=True, include_key=False)
    client = _client(monkeypatch, store, link_only)
    response = client.get("/webapp/api/operator-deep-history", headers={"X-Telegram-Init-Data": "signed"})
    assert response.status_code == 403


def test_premium_is_resolved_server_side_and_client_cannot_self_assert(monkeypatch):
    store = InMemoryStore()
    for idx, outcome in enumerate(["failed", "mixed", "clean", "clean"]):
        _mission(store, idx, outcome)
    entitlements = Entitlements(premium=True)
    client = _client(monkeypatch, store, entitlements)

    response = client.get(
        "/webapp/api/operator-deep-history?premium=true&entitlement=bco_premium",
        headers={"X-Telegram-Init-Data": "signed", "X-Premium": "true"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["premium"] is True
    assert payload["premium_authority"] == "server_bco_premium"
    assert payload["data"]["truth_contract"]["client_premium_authority"] is False
    assert entitlements.calls == [991]


def test_entitlement_outage_fails_closed(monkeypatch):
    store = InMemoryStore()
    client = _client(monkeypatch, store, Entitlements(premium=True, fail=True))
    response = client.get("/webapp/api/operator-deep-history", headers={"X-Telegram-Init-Data": "signed"})
    assert response.status_code == 503
    assert response.json()["detail"] == "premium_authority_unavailable"


def test_untrusted_browser_identity_never_reaches_entitlement_service(monkeypatch):
    store = InMemoryStore()
    entitlements = Entitlements(premium=True)
    monkeypatch.setattr(cc, "verify_init_data", lambda raw: (False, {}))
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=entitlements)
    app = FastAPI()
    app.include_router(cc.router)
    response = TestClient(app).get("/webapp/api/operator-deep-history")
    assert response.status_code == 401
    assert entitlements.calls == []
