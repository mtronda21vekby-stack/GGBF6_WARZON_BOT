from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.operator_intelligence.regime_change import PlayerRegimeChangeDetector
from app.services.storage.memory import InMemoryStore
from app.webapp import command_center_router as cc


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def at_days_ago(days: int, offset: int = 0) -> str:
    return (NOW - timedelta(days=days, minutes=offset)).isoformat()


def history(focus: str, outcomes: list[str], *, days_ago: int = 1, contradictions: set[int] | None = None):
    flags = contradictions or set()
    timeline = [
        {
            "mission_id": f"m{i}",
            "focus": focus,
            "outcome": outcome,
            "at": at_days_ago(days_ago, len(outcomes) - i),
            "vod_correlated": i in flags,
            "contradiction": i in flags,
        }
        for i, outcome in enumerate(outcomes)
    ]
    return {"timeline": timeline}


class Profiles:
    def get(self, chat_id):
        return {}

    def patch(self, chat_id, patch):
        return None


class Entitlements:
    async def get_status(self, user_id: int):
        return SimpleNamespace(premium=True, entitlements=("bco_premium",))


def test_one_session_never_changes_regime():
    snap = PlayerRegimeChangeDetector.snapshot(history("rotations", ["failed"]), now=NOW)
    row = snap["by_focus"]["rotations"]
    assert row["state"] == "insufficient_evidence"
    assert row["comparable_cycles"] == 1
    assert row["one_session_can_change_regime"] is False
    assert snap["truth_contract"]["one_session_can_change_regime"] is False


def test_six_cycles_can_only_create_candidate_shift():
    snap = PlayerRegimeChangeDetector.snapshot(
        history("rotations", ["clean", "clean", "clean", "failed", "failed", "failed"]),
        now=NOW,
    )
    row = snap["by_focus"]["rotations"]
    assert row["state"] == "candidate_shift"
    assert row["direction"] == "declining"
    assert row["comparable_cycles"] == 6
    assert row["cause"] == "unknown"
    assert row["cause_claim"] is False


def test_nine_cycles_two_consecutive_windows_confirm_declining_shift():
    snap = PlayerRegimeChangeDetector.snapshot(
        history(
            "rotations",
            ["clean", "clean", "clean", "failed", "failed", "failed", "failed", "failed", "failed"],
        ),
        now=NOW,
    )
    row = snap["by_focus"]["rotations"]
    assert row["state"] == "confirmed_shift"
    assert row["direction"] == "declining"
    assert row["confidence"] == "high"
    assert row["cause"] == "unknown"
    assert snap["truth_contract"]["shift_does_not_identify_cause"] is True
    assert snap["truth_contract"]["external_meta_change_not_inferred"] is True


def test_reversing_windows_are_volatile_noise_not_confirmed_shift():
    snap = PlayerRegimeChangeDetector.snapshot(
        history(
            "positioning",
            ["mixed", "mixed", "mixed", "clean", "clean", "clean", "failed", "failed", "failed"],
        ),
        now=NOW,
    )
    row = snap["by_focus"]["positioning"]
    assert row["state"] == "volatile_noise"
    assert row["direction"] == "mixed"


def test_recent_vod_contradiction_blocks_regime_confirmation():
    snap = PlayerRegimeChangeDetector.snapshot(
        history(
            "positioning",
            ["clean", "clean", "clean", "failed", "failed", "failed", "failed", "failed", "failed"],
            contradictions={8},
        ),
        now=NOW,
    )
    row = snap["by_focus"]["positioning"]
    assert row["state"] == "contradictory"
    assert row["recent_contradictions"] == 1
    assert snap["truth_contract"]["vod_contradiction_cannot_confirm_shift"] is True
    assert snap["truth_contract"]["explicit_outcome_authoritative"] is True


def test_stale_shift_pattern_remains_candidate_not_current_confirmation():
    snap = PlayerRegimeChangeDetector.snapshot(
        history(
            "rotations",
            ["clean", "clean", "clean", "failed", "failed", "failed", "failed", "failed", "failed"],
            days_ago=30,
        ),
        now=NOW,
    )
    row = snap["by_focus"]["rotations"]
    assert row["state"] == "candidate_shift"
    assert row["direction"] == "declining"
    assert row["freshness"]["state"] == "stale"
    assert row["confirmation_blocked_by_freshness"] is True
    assert snap["truth_contract"]["stale_evidence_cannot_confirm_current_shift"] is True


def test_focuses_do_not_cross_contaminate_regime_windows():
    mixed_timeline = history("rotations", ["clean", "clean", "clean"])["timeline"] + history(
        "positioning", ["clean", "clean", "clean", "failed", "failed", "failed"]
    )["timeline"]
    snap = PlayerRegimeChangeDetector.snapshot({"timeline": mixed_timeline}, now=NOW)
    assert snap["by_focus"]["rotations"]["state"] == "insufficient_evidence"
    assert snap["by_focus"]["positioning"]["state"] == "candidate_shift"


def test_strategy_guard_requires_confirmation_before_strengthening_regression():
    candidate = PlayerRegimeChangeDetector.snapshot(
        history("rotations", ["clean", "clean", "clean", "failed", "failed", "failed"]), now=NOW
    )
    confirmed = PlayerRegimeChangeDetector.snapshot(
        history("rotations", ["clean", "clean", "clean", "failed", "failed", "failed", "failed", "failed", "failed"]), now=NOW
    )
    candidate_guard = PlayerRegimeChangeDetector.strategy_guard(candidate, "regression_intercept", "rotations")
    confirmed_guard = PlayerRegimeChangeDetector.strategy_guard(confirmed, "regression_intercept", "rotations")
    assert candidate_guard["priority_adjustment"] < 0
    assert candidate_guard["reason"] == "candidate_not_confirmed"
    assert confirmed_guard["priority_adjustment"] > 0
    assert confirmed_guard["reason"] == "confirmed_declining_shift"


def test_regime_rollback_preserves_premium_authority_and_disables_only_guard(monkeypatch):
    store = InMemoryStore()
    monkeypatch.setenv("REGIME_CHANGE_DETECTION_ENABLED", "0")
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
    assert payload["regime_authority"] == "disabled_v34_behavior"
    assert payload["data"]["player_regime"]["state"] == "disabled_v34_behavior"
    assert payload["data"]["authority"]["client_authority"] is False
