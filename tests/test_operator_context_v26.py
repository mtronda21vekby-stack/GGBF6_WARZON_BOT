from __future__ import annotations

from types import SimpleNamespace

from app.services.brain.intents import classify_intent
from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.prompt_builder import PromptBuilder
from app.services.brain.response_policy import get_response_policy
from app.services.conversation.service import ConversationService
from app.services.operator_intelligence.context import OperatorContextProjector


def _operator_snapshot():
    return {
        "operator": {
            "readiness": "STABLE",
            "risk": "MODERATE",
            "confidence": "MEDIUM",
            "session_momentum": "IMPROVING",
            "truth_model": {
                "verified_facts": 2,
                "high_confidence_patterns": 1,
                "weak_patterns": 0,
                "hypotheses": 0,
                "unknown_dimensions": 1,
            },
            "dimensions": {
                "rotations": {
                    "assessment": "limiting_signal",
                    "claim_class": "high_confidence_player_pattern",
                    "confidence": "high",
                    "evidence_count": 4,
                    "source_count": 2,
                    "recency_days": 1,
                    "trend": "improving",
                    "uncertainty": "Pattern is strong but not a permanent trait.",
                    "_priority": 999,
                    "evidence": [{
                        "source": "vision_sampled_frames",
                        "fact_class": "high_confidence_pattern",
                        "direction": "risk",
                        "label": "late rotation after low-value chase",
                        "at": "2026-08-17T11:00:00+00:00",
                        "weight": 999,
                    }],
                },
                "tilt_susceptibility": {
                    "assessment": "unknown",
                    "claim_class": "unknown",
                    "confidence": "unknown",
                    "evidence_count": 0,
                    "source_count": 0,
                    "recency_days": None,
                    "trend": "unknown",
                    "uncertainty": "Insufficient evidence.",
                    "evidence": [],
                },
            },
        },
        "mission": {
            "id": "m25-abc",
            "status": "active",
            "focus": "rotations",
            "title": "LATE ROTATION DISCIPLINE",
            "objective": "Rotate before zone pressure and keep strong geometry.",
            "success_condition": "2/3 clean endgames.",
            "confidence": "high",
            "calibration": False,
        },
        "session": {
            "phase": "LIVE_OBJECTIVE",
            "last_review": {"focus": "rotations", "outcome": "mixed", "at": "2026-08-17T10:00:00+00:00"},
            "mission_evidence": {
                "classification": "mission_relevant_evidence_high",
                "confidence": "high",
                "clips": 2,
                "evidence_count": 5,
                "sampled_frames": 8,
                "source": "vision_sampled_frames",
                "latest_at": "2026-08-17T11:30:00+00:00",
                "does_not_complete_mission": True,
                "signals": [{
                    "kind": "timeline",
                    "label": "late rotation after low-value chase",
                    "category": "decision",
                    "confidence": 0.91,
                    "timestamp": "00:17",
                    "weight": 777,
                }],
            },
        },
    }


def test_operator_context_projection_strips_internal_weights_and_preserves_uncertainty():
    projected = OperatorContextProjector().project(_operator_snapshot())
    assert projected["schema"] == "bco_operator_context_v27"
    assert "unknown_remains_unknown" in projected["truth_contract"]
    assert "mission_evidence_does_not_complete" in projected["truth_contract"]
    assert projected["mission"]["status"] == "active"
    assert projected["session"]["phase"] == "LIVE_OBJECTIVE"
    assert projected["claims"][0]["domain"] == "rotations"
    assert projected["claims"][0]["claim_class"] == "high_confidence_player_pattern"
    assert projected["claims"][0]["evidence_count"] == 4
    assert "tilt_susceptibility" in projected["unknown_dimensions"]
    mission_evidence = projected["session"]["mission_evidence"]
    assert mission_evidence["does_not_complete_mission"] is True
    assert mission_evidence["source"] == "vision_sampled_frames"
    rendered = repr(projected)
    assert "_priority" not in rendered
    assert "'weight'" not in rendered
    assert "999" not in rendered
    assert "777" not in rendered


def test_prompt_builder_uses_calibrated_operator_context_and_quarantines_raw_derived_scores():
    profile = {"game": "Warzone", "voice": "COACH", "difficulty": "Pro"}
    intent = classify_intent("Разбери почему я опять поздно ротирую", profile)
    policy = get_response_policy(intent, profile)
    projected = OperatorContextProjector().project(_operator_snapshot())
    player_context = {
        **profile,
        "derived_intelligence": {"dangerous_internal_score": 99, "unbounded_guess": "do-not-pass"},
        "operator_context": projected,
    }
    system = PromptBuilder().build_system(
        profile=profile,
        intent=intent,
        policy=policy,
        knowledge=KnowledgeContext.unknown(),
        emotion_state="neutral",
        emotion_intensity="low",
        player_context=player_context,
    )
    assert "LATE ROTATION DISCIPLINE" in system
    assert "LIVE_OBJECTIVE" in system
    assert "high_confidence_player_pattern" in system
    assert "Unknown dimensions remain unknown" in system
    assert "sampled-frame evidence" in system
    assert "automatic CLEAN/MIXED/FAILED" in system
    assert "dangerous_internal_score" not in system
    assert "unbounded_guess" not in system
    assert "weight=999" not in system


class _Brain:
    def __init__(self):
        self.settings = SimpleNamespace(
            operator_intelligence_enabled=True,
            adaptive_mission_control_enabled=True,
            operator_context_bridge_enabled=True,
        )
        self.last_context = None

    def reply(self, **kwargs):
        self.last_context = dict(kwargs.get("player_context") or {})
        return "ok"


class _Profiles:
    def __init__(self, trusted=True):
        self.trusted = trusted

    def is_trusted_context(self, profile):
        return self.trusted

    def get(self, chat_id):
        return {"game": "Warzone", "_chat_id": chat_id}

    def patch(self, chat_id, patch):
        return None


class _Memory:
    def context(self, chat_id, profile):
        return {**dict(profile), "memory_summary": "trusted memory"}

    def observe(self, **kwargs):
        return None


class _OperatorContext:
    def context(self, chat_id):
        return {"schema": "bco_operator_context_v27", "mission": {"status": "active"}}


class _Store:
    def add(self, *args, **kwargs):
        return None


def test_shared_conversation_boundary_injects_operator_context_only_for_trusted_identity():
    brain = _Brain()
    profiles = _Profiles(trusted=True)
    service = ConversationService(brain=brain, store=_Store(), profiles=profiles)
    service.player_memory = _Memory()
    service.operator_context = _OperatorContext()
    trusted_profile = {"game": "Warzone", "_chat_id": 77}
    assert service.reply(text="что делать", profile=trusted_profile, history=[]) == "ok"
    assert brain.last_context["operator_context"]["schema"] == "bco_operator_context_v27"

    profiles.trusted = False
    brain.last_context = None
    assert service.reply(text="demo", profile={"game": "Warzone", "_chat_id": 999}, history=[]) == "ok"
    assert "operator_context" not in brain.last_context


def test_context_bridge_can_be_rolled_back_without_disabling_operator_twin(monkeypatch):
    monkeypatch.setenv("OPERATOR_CONTEXT_BRIDGE_ENABLED", "0")
    brain = _Brain()
    delattr(brain.settings, "operator_context_bridge_enabled")
    service = ConversationService(brain=brain, store=_Store(), profiles=_Profiles())
    assert service.operator_context is None
