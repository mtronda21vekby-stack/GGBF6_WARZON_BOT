from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.brain.operator_prompt import render_operator_context
from app.services.operator_intelligence import OperatorIntelligenceService
from app.services.operator_intelligence.context import OperatorContextProjector
from app.services.operator_intelligence.mission_orchestrator import MissionOrchestrator
from app.services.storage.memory import InMemoryStore


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


class Profiles:
    def get(self, chat_id):
        return {}

    def patch(self, chat_id, patch):
        return None


def rows(outcomes, *, focus="rotations", days_ago=1, source="explicit_operator_report"):
    result = []
    for i, outcome in enumerate(outcomes):
        result.append({
            "type": "operator_mission",
            "status": "completed",
            "source": source,
            "mission_id": f"m{i}",
            "focus": focus,
            "outcome": outcome,
            "at": (NOW - timedelta(days=days_ago, minutes=len(outcomes) - i)).isoformat(),
        })
    return result


def test_full_explicit_sequence_reaches_maintenance_only_after_stage_gates():
    outcomes = [
        "mixed", "mixed",                    # CALIBRATION -> CORRECTION
        "clean", "clean", "mixed",          # CORRECTION -> VALIDATION
        "clean", "clean",                    # VALIDATION -> STRESS_TEST
        "clean", "clean", "mixed",          # STRESS_TEST -> MAINTENANCE
    ]
    snap = MissionOrchestrator.snapshot(rows(outcomes), "rotations", now=NOW)
    assert snap["stage"] == "MAINTENANCE"
    assert [x["to"] for x in snap["current_transitions"]] == [
        "CORRECTION", "VALIDATION", "STRESS_TEST", "MAINTENANCE"
    ]
    assert snap["current_evaluated_cycles"] == 10
    assert snap["transition_authority"] == "explicit_operator_report_only"
    assert snap["vod_transition_authority"] is False
    assert snap["truth_contract"]["stage_is_training_state_not_player_fact"] is True


def test_one_bad_match_does_not_reset_maintenance_but_repeated_failure_does():
    base = [
        "mixed", "mixed",
        "clean", "clean", "mixed",
        "clean", "clean",
        "clean", "clean", "mixed",
    ]
    one_bad = MissionOrchestrator.snapshot(rows(base + ["failed"]), "rotations", now=NOW)
    assert one_bad["stage"] == "MAINTENANCE"

    repeated = MissionOrchestrator.snapshot(rows(base + ["failed", "clean", "failed"]), "rotations", now=NOW)
    assert repeated["stage"] == "CORRECTION"
    assert repeated["current_transitions"][-1]["reason"] == "maintenance_regression_two_failed_in_three"


def test_reported_without_verdict_and_vod_events_never_advance_stage():
    progression = rows(["reported", "reported"], focus="positioning")
    progression.extend([
        {
            "type": "operator_mission_vod_evidence",
            "status": "observed",
            "source": "vision_sampled_frames",
            "focus": "positioning",
            "outcome": "clean",
            "at": NOW.isoformat(),
        },
        {
            "type": "operator_mission",
            "status": "completed",
            "source": "vision_sampled_frames",
            "focus": "positioning",
            "outcome": "clean",
            "at": NOW.isoformat(),
        },
    ])
    snap = MissionOrchestrator.snapshot(progression, "positioning", now=NOW)
    assert snap["stage"] == "CALIBRATION"
    assert snap["current_evaluated_cycles"] == 0
    assert snap["reported_without_verdict_advances_stage"] is False
    assert snap["truth_contract"]["vod_cannot_advance_stage"] is True


def test_stale_maintenance_history_is_preserved_but_cannot_skip_recalibration():
    historical = [
        "mixed", "mixed",
        "clean", "clean", "mixed",
        "clean", "clean",
        "clean", "clean", "mixed",
    ]
    snap = MissionOrchestrator.snapshot(rows(historical, days_ago=30), "rotations", now=NOW)
    assert snap["historical_stage"] == "MAINTENANCE"
    assert snap["stage"] == "CALIBRATION"
    assert snap["recalibration_required"] is True
    assert snap["stale_explicit_cycles_excluded"] == 10
    assert snap["truth_contract"]["stale_history_is_not_erased"] is True
    assert snap["truth_contract"]["stale_history_cannot_skip_current_recalibration"] is True


def test_two_fresh_baseline_reports_restart_correction_after_stale_history():
    historical = rows([
        "mixed", "mixed", "clean", "clean", "mixed", "clean", "clean", "clean", "clean", "mixed"
    ], days_ago=30)
    fresh = rows(["mixed", "clean"], days_ago=1)
    snap = MissionOrchestrator.snapshot(historical + fresh, "rotations", now=NOW)
    assert snap["historical_stage"] == "MAINTENANCE"
    assert snap["stage"] == "CORRECTION"
    assert snap["recalibration_required"] is False
    assert snap["current_evaluated_cycles"] == 2


def test_generic_calibration_focus_never_auto_promotes_to_correction():
    snap = MissionOrchestrator.snapshot(rows(["clean"] * 12, focus="calibration"), "calibration", now=NOW)
    assert snap["stage"] == "CALIBRATION"
    assert snap["stage_reason"] == "no_evidence_specific_focus_yet"


def test_candidate_decoration_preserves_mission_id_and_adds_explicit_stage_gate():
    mission = {
        "id": "mis_abc",
        "status": "candidate",
        "focus": "rotations",
        "objective": "Hold one rotation rule.",
        "success_condition": "2/3 clean rotations.",
    }
    orch = MissionOrchestrator.snapshot(rows(["mixed", "mixed"]), "rotations", now=NOW)
    decorated = MissionOrchestrator.decorate_candidate(mission, orch)
    assert decorated["id"] == "mis_abc"
    assert decorated["training_stage"] == "CORRECTION"
    assert "STAGE GATE" in decorated["success_condition"]
    assert decorated["orchestrator"]["vod_transition_authority"] is False


def test_package_operator_service_keeps_v28_longitudinal_and_adds_v36_orchestrator():
    service = OperatorIntelligenceService(store=InMemoryStore(), profiles=Profiles())
    snap = service.snapshot(77)
    assert snap["longitudinal"]["schema"] == "bco_longitudinal_operator_v28"
    assert snap["mission_orchestrator"]["enabled"] is True
    assert snap["mission_orchestrator"]["schema"] == "bco_mission_orchestrator_v36"
    assert snap["mission"]["training_stage"] == "CALIBRATION"


def test_v36_rollback_preserves_current_v28_operator_behavior():
    service = OperatorIntelligenceService(
        store=InMemoryStore(),
        profiles=Profiles(),
        orchestrator_enabled=False,
    )
    snap = service.snapshot(77)
    assert snap["longitudinal"]["schema"] == "bco_longitudinal_operator_v28"
    assert snap["mission_orchestrator"] == {
        "enabled": False,
        "schema": "disabled_v35_behavior",
        "transition_authority": "explicit_operator_report_only",
        "vod_transition_authority": False,
    }
    assert "training_stage" not in snap["mission"]


def test_shared_operator_context_projects_stage_without_internal_authority():
    service = OperatorIntelligenceService(store=InMemoryStore(), profiles=Profiles())
    snap = service.snapshot(77)
    projected = OperatorContextProjector().project(snap)
    mission = projected["mission"]
    assert mission["training_stage"] == "CALIBRATION"
    assert mission["orchestrator"]["transition_authority"] == "explicit_operator_report_only"
    assert mission["orchestrator"]["vod_transition_authority"] is False
    prompt = render_operator_context({"operator_context": projected})
    assert "mission_orchestrator:" in prompt
    assert "transition_authority=explicit_operator_report_only" in prompt
    assert "cannot advance the training stage" in prompt
