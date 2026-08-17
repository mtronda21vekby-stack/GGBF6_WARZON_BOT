from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.operator_intelligence.adaptive_strategy import PremiumAdaptiveStrategyService
from app.services.storage.memory import InMemoryStore
from app.webapp import command_center_router as cc


class Profiles:
    def get(self, chat_id):
        return {}

    def patch(self, chat_id, patch):
        return None


class Entitlements:
    def __init__(self, premium=True):
        self.premium = premium
        self.calls = []

    async def get_status(self, user_id: int):
        self.calls.append(user_id)
        return SimpleNamespace(
            premium=self.premium,
            entitlements=("bco_premium",) if self.premium else (),
        )


def test_regression_watch_becomes_next_strategy_without_causal_claim():
    history = {
        "horizon": {"observed_cycles": 12},
        "evidence": {"contradictions": 0},
        "focus_comparisons": [
            {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0, "confidence": "high"},
            {"focus": "movement", "cycles": 4, "direction": "stable", "contradictions": 0, "confidence": "medium"},
        ],
        "signals": {
            "regression_watch": {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0},
            "strongest_improvement": None,
        },
    }
    operator = {"mission": {"focus": "rotations"}, "longitudinal": {"trend": "declining"}}
    data = PremiumAdaptiveStrategyService().build(history, operator)
    assert data["schema"] == "bco_premium_adaptive_strategy_v35"
    assert data["strategy_class"] == "regression_intercept"
    assert data["focus"] == "rotations"
    assert data["mission_alignment"] == "aligned"
    assert data["confidence"] == "high"
    assert data["historical_confidence"] == "high"
    assert data["truth_contract"]["causal_claims"] is False
    assert data["truth_contract"]["strategy_is_recommendation_not_fact"] is True
    assert data["truth_contract"]["portfolio_priority_is_associative"] is True
    assert data["truth_contract"]["exploration_is_deterministic"] is True
    assert data["truth_contract"]["stale_is_not_false"] is True
    assert data["truth_contract"]["one_session_can_change_regime"] is False
    assert data["truth_contract"]["regime_shift_does_not_identify_cause"] is True
    assert data["exploration_budget"]["random_selection"] is False
    assert data["player_regime"]["state"] == "disabled_v34_behavior"
    assert data["authority"]["client_authority"] is False


def test_contradiction_resolution_takes_precedence_when_no_regression():
    history = {
        "horizon": {"observed_cycles": 9},
        "evidence": {"contradictions": 2},
        "focus_comparisons": [
            {"focus": "positioning", "cycles": 7, "direction": "stable", "contradictions": 2},
        ],
        "signals": {"regression_watch": None, "strongest_improvement": None},
    }
    data = PremiumAdaptiveStrategyService().build(history, {})
    assert data["strategy_class"] == "contradiction_resolution"
    assert data["focus"] == "positioning"
    assert "representative VOD evidence" in data["objective"]
    assert data["truth_contract"]["explicit_outcome_authoritative"] is True


def test_insufficient_history_remains_calibration():
    data = PremiumAdaptiveStrategyService().build(
        {"horizon": {"observed_cycles": 2}, "focus_comparisons": [], "evidence": {}, "signals": {}},
        {},
    )
    assert data["strategy_class"] == "calibration"
    assert data["focus"] == "calibration"
    assert data["confidence"] == "low"
    assert "at least 4 completed mission cycles" in data["objective"]
    assert data["portfolio_calibration"]["state"] == "explore"


def test_strategy_api_is_server_premium_gated(monkeypatch):
    store = InMemoryStore()
    monkeypatch.setattr(cc, "verify_init_data", lambda raw: (True, {"chat_id": 77, "user_id": 991}))
    entitled = Entitlements(premium=True)
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=entitled)
    app = FastAPI()
    app.include_router(cc.router)
    response = TestClient(app).get(
        "/webapp/api/operator-strategy?premium=true",
        headers={"X-Telegram-Init-Data": "signed", "X-Premium": "true"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["premium_authority"] == "server_bco_premium"
    assert payload["strategy_authority"] == "evidence_driven_recommendation"
    assert payload["portfolio_authority"] == "associative_outcome_calibration_only"
    assert payload["exploration_authority"] == "deterministic_evidence_backed_rotation_only"
    assert payload["freshness_authority"] == "server_persisted_evidence_timestamps_only"
    assert payload["regime_authority"] == "server_explicit_outcome_windows_only"
    assert payload["data"]["authority"]["client_authority"] is False
    assert payload["data"]["player_regime"]["cause"] == "unknown"
    assert entitled.calls == [991]

    denied = Entitlements(premium=False)
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=denied)
    response = TestClient(app).get(
        "/webapp/api/operator-strategy?premium=true",
        headers={"X-Telegram-Init-Data": "signed", "X-Premium": "true"},
    )
    assert response.status_code == 403
    assert denied.calls == [991]


def test_strategy_api_requires_trusted_telegram_before_entitlement(monkeypatch):
    store = InMemoryStore()
    entitlements = Entitlements(premium=True)
    monkeypatch.setattr(cc, "verify_init_data", lambda raw: (False, {}))
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=entitlements)
    app = FastAPI()
    app.include_router(cc.router)
    response = TestClient(app).get("/webapp/api/operator-strategy")
    assert response.status_code == 401
    assert entitlements.calls == []
