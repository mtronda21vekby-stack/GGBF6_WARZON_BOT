from __future__ import annotations

from app.services.operator_intelligence.adaptive_strategy import PremiumAdaptiveStrategyService
from app.services.operator_intelligence.exploration_budget import AdaptiveExplorationBudget


def candidate(strategy_class, score, base_priority=None):
    return {
        "strategy_class": strategy_class,
        "score": score,
        "base_priority": score if base_priority is None else base_priority,
        "selected": {"focus": strategy_class},
        "rationale": strategy_class,
        "portfolio_adjustment": 0,
    }


def test_top_signal_wins_before_repeat_limit():
    top, meta = AdaptiveExplorationBudget.choose(
        [candidate("regression_intercept", 40), candidate("contradiction_resolution", 36)],
        {"recent_strategy_classes": ["regression_intercept"]},
    )
    assert top["strategy_class"] == "regression_intercept"
    assert meta["reason"] == "top_signal"
    assert meta["rotated"] is False
    assert meta["random_selection"] is False


def test_close_alternate_rotates_after_two_repeats():
    candidates = [candidate("regression_intercept", 40), candidate("contradiction_resolution", 36)]
    portfolio = {"recent_strategy_classes": ["regression_intercept", "regression_intercept"]}
    first, meta1 = AdaptiveExplorationBudget.choose(candidates, portfolio)
    second, meta2 = AdaptiveExplorationBudget.choose(candidates, portfolio)
    assert first["strategy_class"] == "contradiction_resolution"
    assert second["strategy_class"] == "contradiction_resolution"
    assert meta1 == meta2
    assert meta1["reason"] == "bounded_rotation"
    assert meta1["rotated"] is True
    assert meta1["score_gap"] == 4
    assert meta1["deterministic"] is True


def test_strong_signal_gap_is_never_overridden():
    top, meta = AdaptiveExplorationBudget.choose(
        [candidate("regression_intercept", 40), candidate("contradiction_resolution", 30)],
        {"recent_strategy_classes": ["regression_intercept", "regression_intercept"]},
    )
    assert top["strategy_class"] == "regression_intercept"
    assert meta["reason"] == "strong_signal_gap"
    assert meta["rotated"] is False
    assert meta["strong_signal_override"] is True


def test_single_evidence_candidate_is_never_rotated_away():
    top, meta = AdaptiveExplorationBudget.choose(
        [candidate("regression_intercept", 34)],
        {"recent_strategy_classes": ["regression_intercept", "regression_intercept", "regression_intercept"]},
    )
    assert top["strategy_class"] == "regression_intercept"
    assert meta["reason"] == "only_evidence_backed_candidate"
    assert meta["single_candidate_override"] is True
    assert meta["permanent_exclusion"] is False


def test_adaptive_strategy_rotates_only_to_close_real_signal():
    history = {
        "horizon": {"observed_cycles": 12},
        "evidence": {"contradictions": 2},
        "focus_comparisons": [
            {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0},
            {"focus": "positioning", "cycles": 7, "direction": "stable", "contradictions": 2},
        ],
        "signals": {
            "regression_watch": {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0},
            "strongest_improvement": None,
        },
    }
    portfolio = {
        "schema": "bco_strategy_portfolio_v33",
        "recent_strategy_classes": ["regression_intercept", "regression_intercept"],
        "classes": {
            "regression_intercept": {"priority_adjustment": 0, "state": "neutral", "evaluated": 2},
            "contradiction_resolution": {"priority_adjustment": 2, "state": "reinforce", "evaluated": 2},
        },
    }
    data = PremiumAdaptiveStrategyService().build(history, {}, portfolio)
    assert data["schema"] == "bco_premium_adaptive_strategy_v33"
    assert data["strategy_class"] == "contradiction_resolution"
    assert data["focus"] == "positioning"
    assert data["exploration_budget"]["reason"] == "bounded_rotation"
    assert data["exploration_budget"]["rotated"] is True
    assert data["truth_contract"]["exploration_is_deterministic"] is True
    assert data["truth_contract"]["strong_signal_not_overridden_by_exploration"] is True
    assert data["truth_contract"]["causal_claims"] is False


def test_adaptive_strategy_preserves_strong_regression_despite_repeat_streak():
    history = {
        "horizon": {"observed_cycles": 12},
        "evidence": {"contradictions": 1},
        "focus_comparisons": [
            {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0},
            {"focus": "positioning", "cycles": 6, "direction": "stable", "contradictions": 1},
        ],
        "signals": {
            "regression_watch": {"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0},
            "strongest_improvement": None,
        },
    }
    portfolio = {
        "schema": "bco_strategy_portfolio_v33",
        "recent_strategy_classes": ["regression_intercept", "regression_intercept"],
        "classes": {},
    }
    data = PremiumAdaptiveStrategyService().build(history, {}, portfolio)
    assert data["strategy_class"] == "regression_intercept"
    assert data["exploration_budget"]["reason"] == "strong_signal_gap"
    assert data["exploration_budget"]["rotated"] is False
