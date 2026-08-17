from __future__ import annotations

from app.services.operator_intelligence.adaptive_strategy import PremiumAdaptiveStrategyService
from app.services.operator_intelligence.strategy_portfolio import StrategyPortfolioCalibration


def base_history():
    return {
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


def test_one_window_never_deprioritizes_class():
    portfolio = StrategyPortfolioCalibration.snapshot({
        "by_strategy_class": {
            "regression_intercept": {"evaluated": 1, "supported": 0, "mixed": 0, "unsupported": 1},
        }
    })
    row = portfolio["classes"]["regression_intercept"]
    assert row["state"] == "explore"
    assert row["priority_adjustment"] == 0
    assert portfolio["truth_contract"]["insufficient_data_preserves_exploration"] is True


def test_two_supported_windows_reinforce_without_causal_claim():
    portfolio = StrategyPortfolioCalibration.snapshot({
        "by_strategy_class": {
            "consistency_build": {"evaluated": 2, "supported": 2, "mixed": 0, "unsupported": 0},
        }
    })
    row = portfolio["classes"]["consistency_build"]
    assert row["state"] == "reinforce"
    assert row["priority_adjustment"] == 2
    assert portfolio["truth_contract"]["causal_claims"] is False
    assert portfolio["truth_contract"]["no_strategy_class_is_permanently_blocked"] is True


def test_two_unsupported_windows_deprioritize_but_do_not_block():
    portfolio = StrategyPortfolioCalibration.snapshot({
        "by_strategy_class": {
            "regression_intercept": {"evaluated": 2, "supported": 0, "mixed": 0, "unsupported": 2},
        }
    })
    row = portfolio["classes"]["regression_intercept"]
    assert row["state"] == "deprioritize"
    assert row["priority_adjustment"] == -2
    assert portfolio["truth_contract"]["no_strategy_class_is_permanently_blocked"] is True


def test_portfolio_can_change_choice_only_when_evidence_is_competitive():
    portfolio = StrategyPortfolioCalibration.snapshot({
        "by_strategy_class": {
            "regression_intercept": {"evaluated": 2, "supported": 0, "mixed": 0, "unsupported": 2},
            "contradiction_resolution": {"evaluated": 2, "supported": 2, "mixed": 0, "unsupported": 0},
        }
    })
    data = PremiumAdaptiveStrategyService().build(base_history(), {}, portfolio)
    assert data["strategy_class"] == "contradiction_resolution"
    assert data["focus"] == "positioning"
    assert data["portfolio_calibration"]["state"] == "reinforce"
    assert data["portfolio_calibration"]["priority_adjustment"] == 2
    assert data["truth_contract"]["portfolio_priority_is_associative"] is True
    assert data["truth_contract"]["causal_claims"] is False


def test_unsupported_class_still_wins_when_it_is_only_real_signal():
    history = base_history()
    history["evidence"] = {"contradictions": 0}
    history["focus_comparisons"] = [{"focus": "rotations", "cycles": 8, "direction": "declining", "contradictions": 0}]
    portfolio = StrategyPortfolioCalibration.snapshot({
        "by_strategy_class": {
            "regression_intercept": {"evaluated": 4, "supported": 0, "mixed": 0, "unsupported": 4},
        }
    })
    data = PremiumAdaptiveStrategyService().build(history, {}, portfolio)
    assert data["strategy_class"] == "regression_intercept"
    assert data["portfolio_calibration"]["state"] == "deprioritize"
    assert data["truth_contract"]["no_strategy_class_permanently_blocked"] is True
