# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.services.operator_intelligence.evidence_freshness import EvidenceFreshnessPolicy

ORCHESTRATOR_SCHEMA = "bco_mission_orchestrator_v36"
STAGES = ("CALIBRATION", "CORRECTION", "VALIDATION", "STRESS_TEST", "MAINTENANCE")
CURRENT_HORIZON_MAX_DAYS = 21

_STAGE_COPY = {
    "CALIBRATION": {
        "label": "BASELINE CAPTURE",
        "instruction": "Сохраняй один и тот же протокол и собери 2 сопоставимых explicit результата до коррекции.",
        "success": "2 сопоставимых explicit результата CLEAN/MIXED/FAILED; один результат не продвигает стадию.",
        "next": "CORRECTION",
    },
    "CORRECTION": {
        "label": "CONTROLLED CORRECTION",
        "instruction": "Исполняй одно целевое правило без добавления новых переменных, пока коррекция не станет повторяемой.",
        "success": "2 CLEAN из 3 evaluated циклов на одном focus.",
        "next": "VALIDATION",
    },
    "VALIDATION": {
        "label": "REPEATABILITY VALIDATION",
        "instruction": "Повтори ту же коррекцию в сопоставимых условиях; сложность пока не повышается.",
        "success": "2 последовательных CLEAN explicit результата; FAILED возвращает в CORRECTION.",
        "next": "STRESS_TEST",
    },
    "STRESS_TEST": {
        "label": "PRESSURE VALIDATION",
        "instruction": "Сохрани то же правило под более высоким темпом/давлением, не меняя одновременно несколько переменных.",
        "success": "2 CLEAN из 3 stress-test циклов; 2 FAILED из 3 возвращают в VALIDATION.",
        "next": "MAINTENANCE",
    },
    "MAINTENANCE": {
        "label": "MAINTENANCE WINDOW",
        "instruction": "Поддерживай закреплённое правило и не открывай новую коррекцию из-за одного плохого матча.",
        "success": "Стадия сохраняется; 2 FAILED из rolling 3 explicit циклов возвращают в CORRECTION.",
        "next": "MAINTENANCE",
    },
}


def _at(row: Mapping[str, Any]) -> str:
    return str(row.get("at") or row.get("created_at") or "")[:64]


def _outcome(row: Mapping[str, Any]) -> str:
    value = str(row.get("outcome") or "").strip().casefold()
    return value if value in {"clean", "mixed", "failed"} else ""


@dataclass(frozen=True)
class MissionOrchestrator:
    """Deterministic explicit-outcome mission progression.

    The state machine never reads browser claims, VOD classifications, hidden
    scores, or causal hypotheses. Only completed explicit mission outcomes can
    move stages. Historical outcomes remain history, while stale outcomes are
    excluded from the *current* progression horizon.
    """

    @staticmethod
    def _transition(stage: str, stage_outcomes: list[str]) -> tuple[str, list[str], str]:
        if stage == "CALIBRATION":
            if len(stage_outcomes) >= 2:
                return "CORRECTION", [], "two_explicit_baseline_outcomes"
            return stage, stage_outcomes, "collect_two_baseline_outcomes"

        if stage == "CORRECTION":
            window = stage_outcomes[-3:]
            if len(window) >= 3 and window.count("clean") >= 2:
                return "VALIDATION", [], "two_clean_in_three_correction_cycles"
            return stage, stage_outcomes[-3:], "correction_not_yet_repeatable"

        if stage == "VALIDATION":
            if stage_outcomes and stage_outcomes[-1] == "failed":
                return "CORRECTION", [], "validation_failed_return_to_correction"
            if len(stage_outcomes) >= 2 and stage_outcomes[-2:] == ["clean", "clean"]:
                return "STRESS_TEST", [], "two_consecutive_clean_validation_cycles"
            return stage, stage_outcomes[-2:], "validation_requires_two_consecutive_clean"

        if stage == "STRESS_TEST":
            window = stage_outcomes[-3:]
            if len(window) >= 3 and window.count("clean") >= 2:
                return "MAINTENANCE", [], "two_clean_in_three_stress_cycles"
            if len(window) >= 3 and window.count("failed") >= 2:
                return "VALIDATION", [], "stress_failed_return_to_validation"
            return stage, stage_outcomes[-3:], "stress_test_incomplete"

        # MAINTENANCE
        window = stage_outcomes[-3:]
        if len(window) >= 3 and window.count("failed") >= 2:
            return "CORRECTION", [], "maintenance_regression_two_failed_in_three"
        return "MAINTENANCE", stage_outcomes[-3:], "maintenance_holds_without_repeated_failure"

    @classmethod
    def replay(cls, outcomes: Sequence[str]) -> dict[str, Any]:
        stage = "CALIBRATION"
        buffer: list[str] = []
        transitions: list[dict[str, Any]] = []
        evaluated = 0
        for raw in outcomes:
            outcome = str(raw or "").casefold()
            if outcome not in {"clean", "mixed", "failed"}:
                continue
            evaluated += 1
            buffer.append(outcome)
            next_stage, next_buffer, reason = cls._transition(stage, buffer)
            if next_stage != stage:
                transitions.append({
                    "from": stage,
                    "to": next_stage,
                    "reason": reason,
                    "evaluated_cycle": evaluated,
                    "trigger_outcome": outcome,
                })
            stage, buffer = next_stage, next_buffer
        return {
            "stage": stage,
            "stage_outcomes": list(buffer),
            "evaluated_cycles": evaluated,
            "transitions": transitions[-8:],
        }

    @classmethod
    def snapshot(
        cls,
        progression: Sequence[Mapping[str, Any]] | None,
        focus: str,
        *,
        now=None,
    ) -> dict[str, Any]:
        target = str(focus or "calibration").strip().casefold()[:40] or "calibration"
        rows = [dict(row) for row in list(progression or []) if isinstance(row, Mapping)]
        explicit = [
            row for row in rows
            if str(row.get("type") or "") == "operator_mission"
            and str(row.get("status") or "").casefold() == "completed"
            and str(row.get("source") or "") == "explicit_operator_report"
            and str(row.get("focus") or "").strip().casefold() == target
            and _outcome(row)
        ]
        explicit.sort(key=_at)
        historical = cls.replay([_outcome(row) for row in explicit])

        current_rows: list[dict[str, Any]] = []
        stale_count = 0
        unknown_time_count = 0
        for row in explicit:
            freshness = EvidenceFreshnessPolicy.classify(_at(row), now=now)
            state = str(freshness.get("state") or "unknown")
            if state in {"fresh", "aging"} and int(freshness.get("age_days") or 0) <= CURRENT_HORIZON_MAX_DAYS:
                current_rows.append(row)
            elif state == "stale":
                stale_count += 1
            else:
                unknown_time_count += 1

        # Generic calibration has no evidence-specific focus. It remains
        # baseline capture until Operator Twin surfaces a concrete focus.
        if target == "calibration":
            current = cls.replay([])
            current["stage"] = "CALIBRATION"
            stage_reason = "no_evidence_specific_focus_yet"
        else:
            current = cls.replay([_outcome(row) for row in current_rows])
            stage_reason = (
                "current_explicit_outcome_replay"
                if current_rows
                else "fresh_recalibration_required"
            )

        stage = str(current.get("stage") or "CALIBRATION")
        copy = dict(_STAGE_COPY[stage])
        last = current_rows[-1] if current_rows else None
        last_freshness = EvidenceFreshnessPolicy.classify(_at(last or {}), now=now) if last else {
            "state": "unknown", "age_days": None, "evidence_at": None
        }
        return {
            "schema": ORCHESTRATOR_SCHEMA,
            "focus": target,
            "stage": stage,
            "stage_label": copy["label"],
            "instruction": copy["instruction"],
            "stage_success_condition": copy["success"],
            "next_stage_if_passed": copy["next"],
            "stage_reason": stage_reason,
            "current_evaluated_cycles": int(current.get("evaluated_cycles") or 0),
            "current_stage_outcomes": list(current.get("stage_outcomes") or []),
            "current_transitions": list(current.get("transitions") or []),
            "historical_stage": str(historical.get("stage") or "CALIBRATION"),
            "historical_evaluated_cycles": int(historical.get("evaluated_cycles") or 0),
            "historical_transitions": list(historical.get("transitions") or []),
            "stale_explicit_cycles_excluded": stale_count,
            "unknown_time_cycles_excluded": unknown_time_count,
            "latest_current_outcome_at": _at(last or {}) or None,
            "latest_current_outcome_freshness": last_freshness,
            "recalibration_required": target != "calibration" and not current_rows and bool(explicit),
            "transition_authority": "explicit_operator_report_only",
            "vod_transition_authority": False,
            "reported_without_verdict_advances_stage": False,
            "one_result_can_advance_from_calibration": False,
            "truth_contract": {
                "explicit_outcome_authoritative": True,
                "vod_cannot_advance_stage": True,
                "sampled_frame_vod_does_not_autocomplete": True,
                "reported_without_clean_mixed_failed_does_not_advance": True,
                "stale_history_is_not_erased": True,
                "stale_history_cannot_skip_current_recalibration": True,
                "stage_is_training_state_not_player_fact": True,
                "stage_transition_does_not_prove_cause": True,
                "one_bad_match_does_not_reset_maintenance": True,
                "client_authority": False,
            },
        }

    @staticmethod
    def decorate_candidate(mission: Mapping[str, Any], orchestration: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(mission or {})
        orch = dict(orchestration or {})
        stage = str(orch.get("stage") or "CALIBRATION")
        result["orchestrator"] = orch
        result["training_stage"] = stage
        result["stage_label"] = str(orch.get("stage_label") or stage)
        base_objective = str(result.get("objective") or "").strip()
        instruction = str(orch.get("instruction") or "").strip()
        result["objective"] = f"{base_objective}  // {instruction}"[:1000] if instruction else base_objective
        result["stage_success_condition"] = str(orch.get("stage_success_condition") or "")[:700]
        result["base_success_condition"] = str(result.get("success_condition") or "")[:700]
        result["success_condition"] = (
            f"MISSION RULE: {result.get('base_success_condition')}  // STAGE GATE: {result.get('stage_success_condition')}"
        )[:1200]
        result["next_adaptation"] = (
            f"Orchestrator: {stage} → {orch.get('next_stage_if_passed')}. "
            "Stage transition uses explicit CLEAN/MIXED/FAILED reports only; VOD cannot advance it."
        )[:700]
        return result

    @staticmethod
    def annotate_active(mission: Mapping[str, Any], orchestration: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(mission or {})
        if "orchestrator" not in result:
            # Preserve the objective/success contract of a mission accepted
            # before v36. Only add read-only orchestration context.
            result["orchestrator"] = dict(orchestration or {})
            result["training_stage"] = str((orchestration or {}).get("stage") or "CALIBRATION")
            result["stage_label"] = str((orchestration or {}).get("stage_label") or result["training_stage"])
        return result
