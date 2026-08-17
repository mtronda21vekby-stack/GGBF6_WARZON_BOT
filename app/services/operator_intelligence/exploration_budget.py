# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping, Sequence

REPEAT_LIMIT = 2
CLOSE_SCORE_GAP = 6


class AdaptiveExplorationBudget:
    """Deterministically rotate among close evidence-backed strategy candidates.

    This is not random exploration. A repeated class may yield once only when
    another real candidate is close enough in score. Strong evidence gaps and
    single-candidate situations always win. No class is permanently excluded.
    """

    @staticmethod
    def recent_sequence(portfolio: Mapping[str, Any] | None) -> list[str]:
        raw = (portfolio or {}).get("recent_strategy_classes")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            return []
        return [str(x or "").strip()[:40] for x in raw if str(x or "").strip()][-6:]

    @classmethod
    def repeat_streak(cls, portfolio: Mapping[str, Any] | None, strategy_class: str) -> int:
        target = str(strategy_class or "").strip()
        if not target:
            return 0
        streak = 0
        for name in reversed(cls.recent_sequence(portfolio)):
            if name != target:
                break
            streak += 1
        return streak

    @classmethod
    def choose(
        cls,
        candidates: Sequence[Mapping[str, Any]],
        portfolio: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        ranked = sorted(
            [dict(x) for x in candidates if isinstance(x, Mapping)],
            key=lambda x: (int(x.get("score") or 0), int(x.get("base_priority") or 0)),
            reverse=True,
        )
        if not ranked:
            return None, cls._meta("no_candidates", False, 0, None, None, None)

        top = ranked[0]
        top_class = str(top.get("strategy_class") or "")
        streak = cls.repeat_streak(portfolio, top_class)
        if streak < REPEAT_LIMIT:
            return top, cls._meta("top_signal", False, streak, top_class, None, 0)

        alternate = next((row for row in ranked[1:] if str(row.get("strategy_class") or "") != top_class), None)
        if alternate is None:
            return top, cls._meta("only_evidence_backed_candidate", False, streak, top_class, None, None)

        gap = int(top.get("score") or 0) - int(alternate.get("score") or 0)
        if gap > CLOSE_SCORE_GAP:
            return top, cls._meta("strong_signal_gap", False, streak, top_class, str(alternate.get("strategy_class") or ""), gap)

        chosen_class = str(alternate.get("strategy_class") or "")
        return alternate, cls._meta("bounded_rotation", True, streak, top_class, chosen_class, gap)

    @staticmethod
    def _meta(
        reason: str,
        rotated: bool,
        repeat_streak: int,
        original_class: str | None,
        selected_class: str | None,
        score_gap: int | None,
    ) -> dict[str, Any]:
        return {
            "schema": "bco_adaptive_exploration_budget_v33",
            "reason": reason,
            "rotated": bool(rotated),
            "repeat_streak": max(0, int(repeat_streak or 0)),
            "repeat_limit": REPEAT_LIMIT,
            "close_score_gap": CLOSE_SCORE_GAP,
            "original_class": original_class,
            "selected_class": selected_class or original_class,
            "score_gap": score_gap,
            "deterministic": True,
            "random_selection": False,
            "evidence_backed_candidates_only": True,
            "strong_signal_override": True,
            "single_candidate_override": True,
            "permanent_exclusion": False,
            "causal_claims": False,
        }
