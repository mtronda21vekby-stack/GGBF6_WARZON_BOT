from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.operator_intelligence.adaptive_strategy import PremiumAdaptiveStrategyService
from app.services.operator_intelligence.evidence_freshness import EvidenceFreshnessPolicy
from app.services.storage.memory import InMemoryStore
from app.webapp import command_center_router as cc


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def iso_days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


class Profiles:
    def get(self, chat_id):
        return {}

    def patch(self, chat_id, patch):
        return None


class Entitlements:
    async def get_status(self, user_id: int):
        return SimpleNamespace(premium=True, entitlements=("bco_premium",))


def test_freshness_classifies_fresh_aging_and_stale():
    assert EvidenceFreshnessPolicy.classify(iso_days_ago(1), now=NOW)["state"] == "fresh"
    assert EvidenceFreshnessPolicy.classify(iso_days_ago(10), now=NOW)["state"] == "aging"
    assert EvidenceFreshnessPolicy.classify(iso_days_ago(30), now=NOW)["state"] == "stale"


def test_missing_or_invalid_timestamp_remains_unknown_not_stale():
    assert EvidenceFreshnessPolicy.classify(None, now=NOW)["state"] == "unknown"
    assert EvidenceFreshnessPolicy.classify("not-a-date", now=NOW)["state"] == "unknown"
    assert EvidenceFreshnessPolicy.classify((NOW + timedelta(days=2)).isoformat(), now=NOW)["state"] == "unknown"


def test_old_associative_portfolio_prior_decays_toward_neutral_only():
    assert EvidenceFreshnessPolicy.decay_portfolio_adjustment(2, "fresh") == 2
    assert EvidenceFreshnessPolicy.decay_portfolio_adjustment(2, "aging") == 1
    assert EvidenceFreshnessPolicy.decay_portfolio_adjustment(2, "stale") == 0
    assert EvidenceFreshnessPolicy.decay_portfolio_adjustment(-2, "aging") == -1
    assert EvidenceFreshnessPolicy.decay_portfolio_adjustment(-2, "stale") == 0


def test_recommendation_confidence_decays_without_rewriting_historical_confidence():
    assert EvidenceFreshnessPolicy.decay_recommendation_confidence("high", "fresh") == "high"
    assert EvidenceFreshnessPolicy.decay_recommendation_confidence("high", "aging") == "medium"
    assert EvidenceFreshnessPolicy.decay_recommendation_confidence("high", "stale") == "low"
    assert EvidenceFreshnessPolicy.decay_recommendation_confidence("unknown", "stale") == "unknown"


def _history_with_stale_regression_and_fresh_contradiction():
    regression = {
        "focus": "rotations",
        "cycles": 8,
        "direction": "declining",
        "contradictions": 0,
        "latest_at": iso_days_ago(30),
    }
    contradiction = {
        "focus": "positioning",
        "cycles": 7,
        "direction": "stable",
        "contradictions": 2,
        "latest_at": iso_days_ago(1),
    }
    return {
        "horizon": {"observed_cycles": 15},
        "evidence": {"contradictions": 2},
        "focus_comparisons": [regression, contradiction],
        "signals": {"regression_watch": regression, "strongest_improvement": None},
    }


def test_fresh_contradiction_can_outrank_stale_regression_without_declaring_stale_false():
    history = _history_with_stale_regression_and_fresh_contradiction()
    freshness = EvidenceFreshnessPolicy.snapshot(history, {}, now=NOW)
    data = PremiumAdaptiveStrategyService().build(history, {}, {}, freshness)
    assert data["strategy_class"] == "contradiction_resolution"
    assert data["focus"] == "positioning"
    assert data["evidence_freshness"]["signal_state"] == "fresh"
    assert data["truth_contract"]["stale_is_not_false"] is True
    assert data["truth_contract"]["freshness_changes_current_relevance_only"] is True
    assert data["truth_contract"]["causal_claims"] is False


def test_stale_regression_still_wins_when_it_is_the_only_real_signal():
    regression = {
        "focus": "rotations",
        "cycles": 8,
        "direction": "declining",
        "contradictions": 0,
        "latest_at": iso_days_ago(30),
    }
    history = {
        "horizon": {"observed_cycles": 8},
        "evidence": {"contradictions": 0},
        "focus_comparisons": [regression],
        "signals": {"regression_watch": regression, "strongest_improvement": None},
    }
    freshness = EvidenceFreshnessPolicy.snapshot(history, {}, now=NOW)
    data = PremiumAdaptiveStrategyService().build(history, {}, {}, freshness)
    assert data["strategy_class"] == "regression_intercept"
    assert data["evidence_freshness"]["signal_state"] == "stale"
    assert data["historical_confidence"] == "high"
    assert data["confidence"] == "low"
    assert "remains valid history" in data["rationale"]


def test_unknown_freshness_preserves_v33_selection_weight():
    regression = {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0}
    history = {
        "horizon": {"observed_cycles": 8},
        "evidence": {"contradictions": 0},
        "focus_comparisons": [regression],
        "signals": {"regression_watch": regression, "strongest_improvement": None},
    }
    freshness = EvidenceFreshnessPolicy.snapshot(history, {}, now=NOW)
    data = PremiumAdaptiveStrategyService().build(history, {}, {}, freshness)
    assert data["strategy_class"] == "regression_intercept"
    assert data["evidence_freshness"]["signal_state"] == "unknown"
    assert data["confidence"] == data["historical_confidence"] == "high"


def test_freshness_rollback_keeps_premium_authority_and_disables_only_decay(monkeypatch):
    store = InMemoryStore()
    monkeypatch.setenv("EVIDENCE_FRESHNESS_ENABLED", "0")
    monkeypatch.setattr(cc, "verify_init_data", lambda raw: (True, {"chat_id": 77, "user_id": 991}))
    cc.bind_runtime(store=store, profiles=Profiles(), entitlements=Entitlements())
    app = FastAPI()
    app.include_router(cc.router)
    response = TestClient(app).get(
        "/webapp/api/operator-strategy?premium=true",
        headers={"X-Telegram-Init-Data": "signed", "X-Premium": "true"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["premium_authority"] == "server_bco_premium"
    assert payload["freshness_authority"] == "disabled_v33_behavior"
    assert payload["data"]["authority"]["client_authority"] is False
