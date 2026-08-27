from __future__ import annotations

from uuid import uuid4

from app.crown_core.action_planner import CrownActionPlanner
from app.crown_core.action_stream import proposals_from_provider_metadata


def _proposal(text: str, *, report_id=None):
    turn_id = uuid4()
    metadata = CrownActionPlanner().propose(
        text=text,
        source_turn_id=turn_id,
        analysis_report_id=report_id,
    )
    proposals = proposals_from_provider_metadata(metadata, source_turn_id=turn_id)
    return proposals[0] if proposals else None


def test_planner_proposes_relative_reminder_only_for_unambiguous_time():
    proposal = _proposal("Напомни мне через 2 часа проверить сборку")
    assert proposal is not None
    assert proposal.action_id == "reminder.create"
    assert proposal.arguments["schedule"] == {"kind": "relative", "seconds": 7200}
    assert "проверить сборку" in proposal.arguments["title"].lower()

    assert _proposal("Напомни завтра вечером проверить сборку") is None


def test_planner_keeps_tomorrow_clock_time_device_local():
    proposal = _proposal("Напомни завтра в 20:00 потренироваться")
    assert proposal is not None
    assert proposal.action_id == "reminder.create"
    assert proposal.arguments["schedule"] == {
        "kind": "local",
        "days_from_today": 1,
        "hour": 20,
        "minute": 0,
    }
    assert "потренироваться" in proposal.arguments["title"].lower()

    english = _proposal("Remind me tomorrow at 8 pm to train")
    assert english is not None
    assert english.arguments["schedule"] == {
        "kind": "local",
        "days_from_today": 1,
        "hour": 20,
        "minute": 0,
    }

    # Day without an explicit clock time remains clarification-only.
    assert _proposal("Напомни завтра потренироваться") is None


def test_planner_proposes_allowlisted_memory_save_and_forget():
    save = _proposal("Запомни мою цель: выйти в топ-250")
    assert save is not None
    assert save.action_id == "memory.propose_save"
    assert save.arguments == {"field": "current_goal", "value": "выйти в топ-250"}

    forget = _proposal("Забудь мой стиль игры")
    assert forget is not None
    assert forget.action_id == "memory.forget"
    assert forget.arguments == {"field": "playstyle"}


def test_planner_navigation_is_closed_to_known_surfaces():
    proposal = _proposal("Открой штаб")
    assert proposal is not None
    assert proposal.action_id == "app.navigate"
    assert proposal.arguments == {"destination": "war_room"}

    assert _proposal("Открой https://evil.example") is None


def test_planner_analysis_requires_owner_scoped_report_context():
    report_id = uuid4()
    proposal = _proposal("Открой анализ", report_id=report_id)
    assert proposal is not None
    assert proposal.action_id == "analyze.open_report"
    assert proposal.arguments == {"report_id": str(report_id)}

    generic = _proposal("Открой анализ")
    assert generic is not None
    assert generic.action_id == "app.navigate"
    assert generic.arguments == {"destination": "analyze"}


def test_planner_does_not_propose_ambiguous_memory_mutation():
    assert _proposal("Запомни это") is None
    assert _proposal("Забудь это") is None
