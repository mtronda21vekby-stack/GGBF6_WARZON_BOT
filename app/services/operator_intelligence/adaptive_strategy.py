# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence.exploration_budget import AdaptiveExplorationBudget
from app.services.operator_intelligence.strategy_portfolio import StrategyPortfolioCalibration


@dataclass(frozen=True)
class PremiumAdaptiveStrategyService:
    """Build a bounded next-objective strategy from Premium Deep History.

    Entitlement is resolved by the server route before this service is called.
    Portfolio priors and v33 exploration are associative and deterministic:
    repeated strategy classes may rotate only to a close evidence-backed peer.
    """

    def build(self, deep_history: Mapping[str, Any], operator: Mapping[str, Any], portfolio: Mapping[str, Any] | None = None) -> dict[str, Any]:
        history = dict(deep_history or {})
        op = dict(operator or {})
        portfolio_data = dict(portfolio or {})
        comparisons = [dict(x) for x in list(history.get("focus_comparisons") or []) if isinstance(x, Mapping)]
        evidence = history.get("evidence") if isinstance(history.get("evidence"), Mapping) else {}
        signals = history.get("signals") if isinstance(history.get("signals"), Mapping) else {}
        current_mission = op.get("mission") if isinstance(op.get("mission"), Mapping) else {}
        longitudinal = op.get("longitudinal") if isinstance(op.get("longitudinal"), Mapping) else {}
        regression = signals.get("regression_watch") if isinstance(signals.get("regression_watch"), Mapping) else None
        improvement = signals.get("strongest_improvement") if isinstance(signals.get("strongest_improvement"), Mapping) else None
        contradiction_count = max(0, int(evidence.get("contradictions") or 0))
        observed_cycles = max(0, int((history.get("horizon") or {}).get("observed_cycles") or 0)) if isinstance(history.get("horizon"), Mapping) else 0
        candidates: list[dict[str, Any]] = []

        def add_candidate(strategy_class: str, selected: Mapping[str, Any] | None, rationale: str, base_priority: int) -> None:
            adjustment = StrategyPortfolioCalibration.adjustment(portfolio_data, strategy_class)
            candidates.append({"strategy_class": strategy_class, "selected": dict(selected or {}), "rationale": rationale, "base_priority": base_priority, "portfolio_adjustment": adjustment, "score": base_priority + adjustment * 3})

        if regression:
            add_candidate("regression_intercept", regression, "Repeated recent-vs-prior decline is a strong bounded signal in Premium history.", 40)
        if contradiction_count > 0:
            contradiction_candidates = [x for x in comparisons if int(x.get("contradictions") or 0) > 0]
            selected_contradiction = max(contradiction_candidates, key=lambda x: (int(x.get("contradictions") or 0), int(x.get("cycles") or 0)), default=None)
            add_candidate("contradiction_resolution", selected_contradiction, "Explicit outcomes and sampled-frame evidence disagree; resolve uncertainty before increasing difficulty.", 30)
        if comparisons:
            stable = [x for x in comparisons if str(x.get("direction") or "") == "stable"]
            selected_consistency = max(stable or comparisons, key=lambda x: int(x.get("cycles") or 0))
            add_candidate("consistency_build", selected_consistency, "Use a well-supported repeated focus to reduce session-to-session variance.", 20)
        if improvement:
            add_candidate("stability_validation", improvement, "An improving association exists; validate stability before treating it as durable mastery.", 10)

        chosen, exploration = AdaptiveExplorationBudget.choose(candidates, portfolio_data)
        if chosen is not None:
            selected = dict(chosen["selected"])
            strategy_class = str(chosen["strategy_class"])
            rationale = str(chosen["rationale"])
            portfolio_adjustment = int(chosen["portfolio_adjustment"])
            selection_score = int(chosen["score"])
            if exploration.get("rotated") is True:
                rationale += " Deterministic exploration rotated to a close evidence-backed alternative after repeated use of the top class."
        else:
            selected = {}
            strategy_class = "calibration"
            rationale = "Insufficient repeated evidence; remain in calibration."
            portfolio_adjustment = StrategyPortfolioCalibration.adjustment(portfolio_data, strategy_class)
            selection_score = portfolio_adjustment * 3

        focus = str(selected.get("focus") or current_mission.get("focus") or "calibration").strip().casefold()[:40]
        selected_cycles = max(0, int(selected.get("cycles") or 0))
        contradictions = max(0, int(selected.get("contradictions") or contradiction_count))
        if selected_cycles >= 8 and contradictions == 0: confidence = "high"
        elif selected_cycles >= 4: confidence = "medium"
        elif observed_cycles: confidence = "low"
        else: confidence = "unknown"

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
        mission_alignment = "aligned" if active_focus and active_focus == focus else ("different_active_focus" if active_focus else "none")
        class_row = ((portfolio_data.get("classes") or {}).get(strategy_class) or {}) if isinstance(portfolio_data.get("classes"), Mapping) else {}
        return {
            "schema": "bco_premium_adaptive_strategy_v33", "strategy_class": strategy_class, "focus": focus, "confidence": confidence,
            "rationale": rationale, "objective": objective, "success_condition": success_condition, "next_adaptation": next_adaptation,
            "mission_alignment": mission_alignment,
            "portfolio_calibration": {"schema": str(portfolio_data.get("schema") or "bco_strategy_portfolio_v32"), "state": str(class_row.get("state") or "explore"), "evaluated_windows": max(0, int(class_row.get("evaluated") or 0)), "priority_adjustment": portfolio_adjustment, "selection_score": selection_score, "insufficient_data_preserves_exploration": True},
            "exploration_budget": exploration,
            "evidence": {"observed_cycles": observed_cycles, "focus_cycles": selected_cycles, "contradictions": contradictions, "longitudinal_trend": str(longitudinal.get("trend") or "unknown")[:24], "source": "server_authorized_deep_history"},
            "authority": {"premium_required": True, "expected_entitlement": "bco_premium", "client_authority": False},
            "truth_contract": {"association_not_causation": True, "causal_claims": False, "explicit_outcome_authoritative": True, "sampled_frame_vod_does_not_autocomplete": True, "strategy_is_recommendation_not_fact": True, "portfolio_priority_is_associative": True, "exploration_is_deterministic": True, "exploration_requires_evidence_backed_alternative": True, "strong_signal_not_overridden_by_exploration": True, "no_strategy_class_permanently_blocked": True},
        }
