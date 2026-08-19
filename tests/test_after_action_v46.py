import asyncio
from pathlib import Path

import app.services.after_action as aa


class DummyStore:
    pass


class DummyProfiles:
    pass


class FakeSessionService:
    calls = 0

    def __init__(self, **kwargs):
        pass

    async def snapshot(self, **kwargs):
        self.__class__.calls += 1
        if self.__class__.calls == 1:
            return {
                "personal_meta": {"coverage": 40, "scores": {"aim": 60}, "top_mistakes": [{"label": "late rotation"}]},
                "operator_twin": {"readiness": "CALIBRATING"},
                "player": {"vod_reviews": []},
            }
        return {
            "personal_meta": {"coverage": 47, "scores": {"aim": 64}, "top_mistakes": [{"label": "late rotation"}, {"label": "repeat peek"}]},
            "operator_twin": {"readiness": "READY"},
            "player": {"vod_reviews": [{"game": "Warzone", "summary": "Repeated same-angle re-peek", "confirmed_mistakes": ["repeat peek"]}]},
            "next_mission": {"id": "next_1", "title": "EXIT VECTOR", "status": "candidate"},
        }


class FakeOperator:
    def complete(self, chat_id, mission_id, **kwargs):
        assert chat_id == 42
        assert mission_id == "mission_1"
        assert kwargs["outcome"] == "mixed"
        return {"next_mission": {"id": "next_1", "title": "EXIT VECTOR"}}


class FakeOperatorFactory:
    @classmethod
    def from_components(cls, **kwargs):
        return FakeOperator()


class FakeStrategy:
    def __init__(self, store):
        pass

    def snapshot(self, chat_id):
        return {"latest": {"verdict": "mixed_association", "causal_claim": False}}


def test_after_action_closes_explicit_cycle_without_causal_or_vod_claims(monkeypatch):
    FakeSessionService.calls = 0
    monkeypatch.setattr(aa, "CrownSessionService", FakeSessionService)
    monkeypatch.setattr(aa, "OrchestratedOperatorIntelligenceService", FakeOperatorFactory)
    monkeypatch.setattr(aa, "PremiumStrategyOutcomeService", FakeStrategy)

    result = asyncio.run(aa.CrownAfterActionService(store=DummyStore(), profiles=DummyProfiles()).complete(
        chat_id=42,
        telegram_user_id=42,
        mission_id="mission_1",
        outcome="mixed",
        metrics={"clean_executions": 2},
    ))

    assert result["schema"] == "crown-after-action-v1"
    assert result["mission_outcome"]["explicit_operator_report"] is True
    assert result["mission_outcome"]["vod_auto_complete"] is False
    assert result["truth_contract"]["vod_evidence_only"] is True
    assert result["truth_contract"]["causal_claims"] is False
    assert result["strategy_outcome"]["association_not_causation"] is True
    assert result["new_weaknesses"] == ["repeat peek"]
    assert result["what_changed"]["coverage_before"] == 40
    assert result["what_changed"]["coverage_after"] == 47
    assert result["what_changed"]["score_changes"][0]["delta"] == 4.0
    assert result["latest_vod_evidence"]["auto_completed_mission"] is False
    assert result["next_mission"]["title"] == "EXIT VECTOR"


def test_after_action_surface_and_boot_order_are_locked():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app/webapp/static/app.js").read_text(encoding="utf-8")
    ui = (root / "app/webapp/static/bco.after-action.js").read_text(encoding="utf-8")
    router = (root / "app/webapp/command_center_router.py").read_text(encoding="utf-8")

    assert app.index("bco.session-home.js") < app.index("bco.after-action.js") < app.index("bco.operator.js")
    assert "/webapp/api/crown-session/after-action" in ui
    assert "/webapp/api/crown-session/after-action" in router
    assert "VOD may support evidence but never completes the mission automatically" in ui
    assert 'data-outcome="clean"' in ui
    assert 'data-outcome="mixed"' in ui
    assert 'data-outcome="failed"' in ui
