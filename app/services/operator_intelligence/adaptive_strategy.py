# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PremiumAdaptiveStrategyService:
    """Build a bounded next-objective strategy from Premium Deep History.

    Entitlement is resolved by the server route before this service is called.
    This layer never accepts a Premium flag and never turns association into
    causation. It chooses a measurable next focus from observed history only.
    """

    def build(self, deep_history: Mapping[str, Any], operator: Mapping[str, Any]) -> dict[str, Any]:
        history = dict(deep_history or {})
        op = dict(operator or {})
        comparisons = [dict(x) for x in list(history.get("focus_comparisons") or []) if isinstance(x, Mapping)]
        evidence = history.get("evidence") if isinstance(history.get("evidence"), Mapping) else {}
        signals = history.get("signals") if isinstance(history.get("signals"), Mapping) else {}
        current_mission = op.get("mission") if isinstance(op.get("mission"), Mapping) else {}
        longitudinal = op.get("longitudinal") if isinstance(op.get("longitudinal"), Mapping) else {}

        regression = signals.get("regression_watch") if isinstance(signals.get("regression_watch"), Mapping) else None
        improvement = signals.get("strongest_improvement") if isinstance(signals.get("strongest_improvement"), Mapping) else None
        contradiction_count = max(0, int(evidence.get("contradictions") or 0))
        observed_cycles = max(0, int((history.get("horizon") or {}).get("observed_cycles") or 0)) if isinstance(history.get("horizon"), Mapping) else 0

        selected: dict[str, Any] | None = None
        rationale = ""
        strategy_class = "calibration"

        if regression:
            selected = dict(regression)
            strategy_class = "regression_intercept"
            rationale = "Repeated recent-vs-prior decline is the strongest bounded signal in Premium history."
        elif contradiction_count > 0:
            candidates = [x for x in comparisons if int(x.get("contradictions") or 0) > 0]
            if candidates:
                selected = max(candidates, key=lambda x: (int(x.get("contradictions") or 0), int(x.get("cycles") or 0)))
            strategy_class = "contradiction_resolution"
            rationale = "Explicit outcomes and sampled-frame evidence disagree; resolve the uncertainty before increasing difficulty."
        elif comparisons:
            stable = [x for x in comparisons if str(x.get("direction") or "") == "stable"]
            selected = max(stable or comparisons, key=lambda x: int(x.get("cycles") or 0))
            strategy_class = "consistency_build"
            rationale = "No regression dominates; use the best-supported repeated focus to improve consistency."
        elif improvement:
            selected = dict(improvement)
            strategy_class = "stability_validation"
            rationale = "An improving association exists, but history is not yet deep enough to treat it as stable mastery."

        focus = str((selected or {}).get("focus") or current_mission.get("focus") or "calibration").strip().casefold()[:40]
        selected_cycles = max(0, int((selected or {}).get("cycles") or 0))
        contradictions = max(0, int((selected or {}).get("contradictions") or contradiction_count))

        if selected_cycles >= 8 and contradictions == 0:
            confidence = "high"
        elif selected_cycles >= 4:
            confidence = "medium"
        elif observed_cycles:
            confidence = "low"
        else:
            confidence = "unknown"

        if focus == "calibration":
            objective = "Collect at least 4 completed mission cycles on one repeated competitive focus before adapting strategy."
            success_condition = "4 comparable explicit mission outcomes with no automatic VOD verdict."
            next_adaptation = "Choose the first focus that reaches a sufficient comparison window."
        else:
            readable = focus.replace("_", " ").upper()
            if strategy_class == "regression_intercept":
                objective = f"Run 3 deliberate {readable} executions while preserving the decision rule that previously worked."
                success_condition = "At least 2/3 explicit clean executions without a new high-confidence contradiction."
                next_adaptation = "If the regression clears across the next comparable window, move from recovery to consistency validation."
            elif strategy_class == "contradiction_resolution":
                objective = f"Run 3 controlled {readable} executions and explicitly report outcome while collecting representative VOD evidence."
                success_condition = "Two comparable sessions where explicit result and sampled-frame evidence no longer materially conflict."
                next_adaptation = "Recalculate confidence only after contradiction density falls; do not auto-promote a CLEAN report."
            elif strategy_class == "stability_validation":
                objective = f"Repeat {readable} under comparable pressure without changing the successful decision rule."
                success_condition = "3 additional comparable outcomes that preserve the improving direction without contradictory VOD evidence."
                next_adaptation = "Only then consider increasing mission difficulty or shifting focus."
            else:
                objective = f"Run 3 comparable {readable} executions with one fixed decision rule to reduce session-to-session variance."
                success_condition = "2/3 clean executions and no increase in contradiction count."
                next_adaptation = "If stable, shift to the next strongest limiting signal; if volatile, keep the same focus."

        active_focus = str(current_mission.get("focus") or "").strip().casefold()
        mission_alignment = "none"
        if active_focus and active_focus == focus:
            mission_alignment = "aligned"
        elif active_focus:
            mission_alignment = "different_active_focus"

        return {
            "schema": "bco_premium_adaptive_strategy_v30",
            "strategy_class": strategy_class,
            "focus": focus,
            "confidence": confidence,
            "rationale": rationale or "Insufficient repeated evidence; remain in calibration.",
            "objective": objective,
            "success_condition": success_condition,
            "next_adaptation": next_adaptation,
            "mission_alignment": mission_alignment,
            "evidence": {
                "observed_cycles": observed_cycles,
                "focus_cycles": selected_cycles,
                "contradictions": contradictions,
                "longitudinal_trend": str(longitudinal.get("trend") or "unknown")[:24],
                "source": "server_authorized_deep_history",
            },
            "authority": {
                "premium_required": True,
                "expected_entitlement": "bco_premium",
                "client_authority": False,
            },
            "truth_contract": {
                "association_not_causation": True,
                "causal_claims": False,
                "explicit_outcome_authoritative": True,
                "sampled_frame_vod_does_not_autocomplete": True,
                "strategy_is_recommendation_not_fact": True,
            },
        }
