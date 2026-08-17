# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

MIN_EVALUATED_WINDOWS = 2


class StrategyPortfolioCalibration:
    """Convert v31 associative outcome evidence into bounded strategy-class priors.

    This layer does not claim a strategy caused later outcomes. It only changes
    selection priority after enough evaluated windows exist. Insufficient data
    remains exploratory and never blocks a class outright.
    """

    @staticmethod
    def snapshot(effectiveness: Mapping[str, Any] | None) -> dict[str, Any]:
        source = dict(effectiveness or {})
        by_class = source.get("by_strategy_class") if isinstance(source.get("by_strategy_class"), Mapping) else {}
        classes: dict[str, dict[str, Any]] = {}
        for raw_name, raw_stats in dict(by_class or {}).items():
            name = str(raw_name or "").strip()[:40]
            if not name or not isinstance(raw_stats, Mapping):
                continue
            stats = dict(raw_stats)
            evaluated = max(0, int(stats.get("evaluated") or 0))
            supported = max(0, int(stats.get("supported") or 0))
            mixed = max(0, int(stats.get("mixed") or 0))
            unsupported = max(0, int(stats.get("unsupported") or 0))

            if evaluated < MIN_EVALUATED_WINDOWS:
                state = "explore"
                adjustment = 0
            elif supported >= 2 and unsupported == 0:
                state = "reinforce"
                adjustment = 2
            elif unsupported >= 2 and supported == 0:
                state = "deprioritize"
                adjustment = -2
            elif supported > unsupported:
                state = "prefer"
                adjustment = 1
            elif unsupported > supported:
                state = "caution"
                adjustment = -1
            else:
                state = "neutral"
                adjustment = 0

            classes[name] = {
                "evaluated": evaluated,
                "supported": supported,
                "mixed": mixed,
                "unsupported": unsupported,
                "state": state,
                "priority_adjustment": adjustment,
                "minimum_evaluated_windows": MIN_EVALUATED_WINDOWS,
            }

        return {
            "schema": "bco_strategy_portfolio_v32",
            "minimum_evaluated_windows": MIN_EVALUATED_WINDOWS,
            "classes": classes,
            "truth_contract": {
                "association_not_causation": True,
                "causal_claims": False,
                "insufficient_data_preserves_exploration": True,
                "no_strategy_class_is_permanently_blocked": True,
                "explicit_outcome_authoritative": True,
            },
        }

    @staticmethod
    def adjustment(portfolio: Mapping[str, Any] | None, strategy_class: str) -> int:
        classes = (portfolio or {}).get("classes") if isinstance((portfolio or {}).get("classes"), Mapping) else {}
        row = classes.get(str(strategy_class or "")) if isinstance(classes, Mapping) else None
        if not isinstance(row, Mapping):
            return 0
        return max(-2, min(2, int(row.get("priority_adjustment") or 0)))
