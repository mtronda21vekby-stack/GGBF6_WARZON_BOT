# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence.evidence_freshness import EvidenceFreshnessPolicy
from app.services.operator_intelligence.exploration_budget import AdaptiveExplorationBudget
from app.services.operator_intelligence.regime_change import PlayerRegimeChangeDetector
from app.services.operator_intelligence.strategy_portfolio import StrategyPortfolioCalibration


@dataclass(frozen=True)
class PremiumAdaptiveStrategyService:
    """Build a bounded next-objective strategy from Premium Deep History.

    Entitlement is resolved by the server route before this service is called.
    v32 portfolio priors remain associative, v33 exploration deterministic,
    v34 freshness changes current relevance only, and v35 regime detection can
    guard against reacting to unsustained behavioral change without assigning
    a cause to that change.
    """

    def build(
        self,
        deep_history: Mapping[str, Any],
        operator: Mapping[str, Any],
        portfolio: Mapping[str, Any] | None = None,
        freshness: Mapping[str, Any] | None = None,
        regime: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        history = dict(deep_history or {})
        op = dict(operator or {})
        portfolio_data = dict(portfolio or {})
        freshness_data = dict(freshness or {})
        regime_enabled = regime is not None
        regime_data = dict(regime or {})
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

        def regime_guard(strategy_class: str, focus_name: str) -> dict[str, Any]:
            if not regime_enabled:
                return {
                    "state": "disabled_v34_behavior",
                    "direction": "unknown",
                    "confidence": "unknown",
                    "cause": "unknown",
                    "cause_claim": False,
                    "priority_adjustment": 0,
                    "reason": "regime_detection_disabled",
                    "one_session_can_change_regime": False,
                }
            return PlayerRegimeChangeDetector.strategy_guard(regime_data, strategy_class, focus_name)

        def add_candidate(
            strategy_class: str,
            selected: Mapping[str, Any] | None,
            rationale: str,
            base_priority: int,
        ) -> None:
            selected_data = dict(selected or {})
            focus_name = str(selected_data.get("focus") or "").strip().casefold()[:40]
            historical_adjustment = StrategyPortfolioCalibration.adjustment(portfolio_data, strategy_class)
            class_freshness = EvidenceFreshnessPolicy.strategy_class_row(freshness_data, strategy_class)
            signal_freshness = EvidenceFreshnessPolicy.focus_row(freshness_data, focus_name)
            effective_adjustment = EvidenceFreshnessPolicy.decay_portfolio_adjustment(
                historical_adjustment,
                str(class_freshness.get("state") or "unknown"),
            )
            signal_adjustment = EvidenceFreshnessPolicy.signal_priority_adjustment(
                str(signal_freshness.get("state") or "unknown")
            )
            guard = regime_guard(strategy_class, focus_name)
            regime_adjustment = int(guard.get("priority_adjustment") or 0)
            candidates.append({
                "strategy_class": strategy_class,
                "selected": selected_data,
                "rationale": rationale,
                "base_priority": base_priority,
                "portfolio_adjustment": effective_adjustment,
                "historical_portfolio_adjustment": historical_adjustment,
                "freshness_adjustment": signal_adjustment,
                "regime_adjustment": regime_adjustment,
                "regime_guard": guard,
                "signal_freshness": signal_freshness,
                "portfolio_freshness": class_freshness,
                "score": base_priority + signal_adjustment + effective_adjustment * 3 + regime_adjustment,
            })

        if regression:
            add_candidate(
                "regression_intercept",
                regression,
                "Repeated recent-vs-prior decline is a strong bounded signal in Premium history.",
                40,
            )

        if contradiction_count > 0:
            contradiction_candidates = [x for x in comparisons if int(x.get("contradictions") or 0) > 0]
            selected_contradiction = max(
                contradiction_candidates,
                key=lambda x: (int(x.get("contradictions") or 0), int(x.get("cycles") or 0)),
                default=None,
            )
            add_candidate(
                "contradiction_resolution",
                selected_contradiction,
                "Explicit outcomes and sampled-frame evidence disagree; resolve uncertainty before increasing difficulty.",
                30,
            )

        if comparisons:
            stable = [x for x in comparisons if str(x.get("direction") or "") == "stable"]
            selected_consistency = max(stable or comparisons, key=lambda x: int(x.get("cycles") or 0))
            add_candidate(
                "consistency_build",
                selected_consistency,
                "Use a well-supported repeated focus to reduce session-to-session variance.",
                20,
            )

        if improvement:
            add_candidate(
                "stability_validation",
                improvement,
                "An improving association exists; validate stability before treating it as durable mastery.",
                10,
            )

        chosen, exploration = AdaptiveExplorationBudget.choose(candidates, portfolio_data)
        if chosen is not None:
            selected = dict(chosen["selected"])
            strategy_class = str(chosen["strategy_class"])
            rationale = str(chosen["rationale"])
            portfolio_adjustment = int(chosen["portfolio_adjustment"])
            historical_portfolio_adjustment = int(chosen.get("historical_portfolio_adjustment") or 0)
            selection_score = int(chosen["score"])
            signal_freshness = dict(chosen.get("signal_freshness") or {})
            portfolio_freshness = dict(chosen.get("portfolio_freshness") or {})
            freshness_adjustment = int(chosen.get("freshness_adjustment") or 0)
            selected_regime = dict(chosen.get("regime_guard") or {})
            if exploration.get("rotated") is True:
                rationale += " Deterministic exploration rotated to a close evidence-backed alternative after repeated use of the top class."
            freshness_state = str(signal_freshness.get("state") or "unknown")
            if freshness_state == "aging":
                rationale += " The evidence is aging, so current relevance and recommendation confidence are reduced without rewriting history."
            elif freshness_state == "stale":
                rationale += " The evidence is stale: it remains valid history, but it no longer carries full current-strategy weight."
            regime_state = str(selected_regime.get("state") or "insufficient_evidence")
            if regime_state == "confirmed_shift":
                rationale += " A sustained behavioral regime shift is confirmed across consecutive windows; its cause remains unknown."
            elif regime_state in {"candidate_shift", "volatile_noise", "stable_baseline", "contradictory", "insufficient_evidence"} and int(selected_regime.get("priority_adjustment") or 0) < 0:
                rationale += " Regime guard reduced reaction strength because the behavioral change is not yet sustained and confirmed."
        else:
            selected = {}
            strategy_class = "calibration"
            rationale = "Insufficient repeated evidence; remain in calibration."
            historical_portfolio_adjustment = StrategyPortfolioCalibration.adjustment(portfolio_data, strategy_class)
            class_freshness = EvidenceFreshnessPolicy.strategy_class_row(freshness_data, strategy_class)
            portfolio_adjustment = EvidenceFreshnessPolicy.decay_portfolio_adjustment(
                historical_portfolio_adjustment,
                str(class_freshness.get("state") or "unknown"),
            )
            selection_score = portfolio_adjustment * 3
            signal_freshness = {"state": "unknown", "age_days": None, "evidence_at": None}
            portfolio_freshness = class_freshness
            freshness_adjustment = 0
            selected_regime = regime_guard(strategy_class, "calibration")

        focus = str(selected.get("focus") or current_mission.get("focus") or "calibration").strip().casefold()[:40]
        selected_cycles = max(0, int(selected.get("cycles") or 0))
        contradictions = max(0, int(selected.get("contradictions") or contradiction_count))

        if selected_cycles >= 8 and contradictions == 0:
            historical_confidence = "high"
        elif selected_cycles >= 4:
            historical_confidence = "medium"
        elif observed_cycles:
            historical_confidence = "low"
        else:
            historical_confidence = "unknown"
        confidence = EvidenceFreshnessPolicy.decay_recommendation_confidence(
            historical_confidence,
            str(signal_freshness.get("state") or "unknown"),
        )

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
            "schema": "bco_premium_adaptive_strategy_v35",
            "strategy_class": strategy_class,
            "focus": focus,
            "confidence": confidence,
            "historical_confidence": historical_confidence,
            "rationale": rationale,
            "objective": objective,
            "success_condition": success_condition,
            "next_adaptation": next_adaptation,
            "mission_alignment": mission_alignment,
            "portfolio_calibration": {
                "schema": str(portfolio_data.get("schema") or "bco_strategy_portfolio_v32"),
                "state": str(class_row.get("state") or "explore"),
                "evaluated_windows": max(0, int(class_row.get("evaluated") or 0)),
                "priority_adjustment": portfolio_adjustment,
                "historical_priority_adjustment": historical_portfolio_adjustment,
                "selection_score": selection_score,
                "insufficient_data_preserves_exploration": True,
            },
            "exploration_budget": exploration,
            "evidence_freshness": {
                "schema": str(freshness_data.get("schema") or "bco_evidence_freshness_v34"),
                "signal_state": str(signal_freshness.get("state") or "unknown"),
                "signal_age_days": signal_freshness.get("age_days"),
                "signal_evidence_at": signal_freshness.get("evidence_at"),
                "signal_priority_adjustment": freshness_adjustment,
                "portfolio_state": str(portfolio_freshness.get("state") or "unknown"),
                "portfolio_age_days": portfolio_freshness.get("age_days"),
                "portfolio_evidence_at": portfolio_freshness.get("evidence_at"),
                "stale_is_not_false": True,
                "old_support_is_not_current_proof": True,
            },
            "player_regime": {
                "schema": str(regime_data.get("schema") or ("bco_player_regime_change_v35" if regime_enabled else "disabled_v34_behavior")),
                "state": str(selected_regime.get("state") or "insufficient_evidence"),
                "direction": str(selected_regime.get("direction") or "unknown"),
                "confidence": str(selected_regime.get("confidence") or "unknown"),
                "cause": "unknown",
                "cause_claim": False,
                "selection_guard_reason": str(selected_regime.get("reason") or "neutral"),
                "one_session_can_change_regime": False,
            },
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
                "portfolio_priority_is_associative": True,
                "exploration_is_deterministic": True,
                "exploration_requires_evidence_backed_alternative": True,
                "strong_signal_not_overridden_by_exploration": True,
                "no_strategy_class_permanently_blocked": True,
                "stale_is_not_false": True,
                "freshness_changes_current_relevance_only": True,
                "missing_timestamp_remains_unknown": True,
                "old_support_is_not_current_proof": True,
                "one_session_can_change_regime": False,
                "regime_shift_does_not_identify_cause": True,
                "external_meta_change_not_inferred": True,
                "stale_evidence_cannot_confirm_current_shift": True,
                "vod_contradiction_cannot_confirm_shift": True,
            },
        }
