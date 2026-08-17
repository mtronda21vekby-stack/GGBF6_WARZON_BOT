# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Mapping

from app.services.operator_intelligence.evidence_freshness import EvidenceFreshnessPolicy

MIN_CANDIDATE_CYCLES = 6
MIN_CONFIRMED_CYCLES = 9
WINDOW_SIZE = 3
SHIFT_DELTA = 2.0 / 3.0


def _score(outcome: str) -> float:
    return {"clean": 1.0, "mixed": 0.0, "failed": -1.0}.get(str(outcome or "").casefold(), 0.0)


def _direction(delta: float) -> str:
    if delta >= SHIFT_DELTA:
        return "improving"
    if delta <= -SHIFT_DELTA:
        return "declining"
    return "stable"


def _same_shift(a: str, b: str) -> bool:
    return a in {"improving", "declining"} and a == b


class PlayerRegimeChangeDetector:
    """Detect sustained player-behavior shifts without attributing cause.

    This detector consumes only server-persisted explicit mission outcomes and
    the existing sampled-frame contradiction marker. It can describe a
    sustained behavioral shift, but it cannot infer that tilt, a game-meta
    change, coaching, or any other cause produced that shift.
    """

    @classmethod
    def _focus_snapshot(cls, focus: str, cycles: list[dict[str, Any]], *, now=None) -> dict[str, Any]:
        usable = [
            dict(row) for row in cycles
            if str(row.get("outcome") or "").casefold() in {"clean", "mixed", "failed"}
        ][-MIN_CONFIRMED_CYCLES:]
        latest_at = str(usable[-1].get("at") or "")[:64] if usable else ""
        freshness = EvidenceFreshnessPolicy.classify(latest_at, now=now)
        recent_three = usable[-WINDOW_SIZE:] if len(usable) >= WINDOW_SIZE else usable
        recent_contradictions = sum(1 for row in recent_three if bool(row.get("contradiction")))

        base = {
            "focus": focus,
            "state": "insufficient_evidence",
            "direction": "unknown",
            "confidence": "unknown",
            "comparable_cycles": len(usable),
            "minimum_candidate_cycles": MIN_CANDIDATE_CYCLES,
            "minimum_confirmed_cycles": MIN_CONFIRMED_CYCLES,
            "window_size": WINDOW_SIZE,
            "freshness": freshness,
            "recent_contradictions": recent_contradictions,
            "cause": "unknown",
            "cause_claim": False,
            "confirmation_blocked_by_freshness": False,
            "one_session_can_change_regime": False,
        }
        if len(usable) < MIN_CANDIDATE_CYCLES:
            return base

        # A current sampled-frame contradiction means regime evidence disagrees
        # across sources. Explicit mission outcome remains authoritative, but a
        # regime shift is not confirmed while that disagreement is unresolved.
        if recent_contradictions > 0:
            base.update({
                "state": "contradictory",
                "direction": "unknown",
                "confidence": "low",
            })
            return base

        if len(usable) >= MIN_CONFIRMED_CYCLES:
            block = usable[-MIN_CONFIRMED_CYCLES:]
            baseline = [_score(row.get("outcome")) for row in block[:WINDOW_SIZE]]
            window_a = [_score(row.get("outcome")) for row in block[WINDOW_SIZE:WINDOW_SIZE * 2]]
            window_b = [_score(row.get("outcome")) for row in block[WINDOW_SIZE * 2:WINDOW_SIZE * 3]]
            baseline_mean = mean(baseline)
            delta_a = mean(window_a) - baseline_mean
            delta_b = mean(window_b) - baseline_mean
            direction_a = _direction(delta_a)
            direction_b = _direction(delta_b)

            base["windows"] = {
                "baseline": {"cycles": WINDOW_SIZE, "mean": round(baseline_mean, 3)},
                "candidate_a": {"cycles": WINDOW_SIZE, "delta": round(delta_a, 3), "direction": direction_a},
                "candidate_b": {"cycles": WINDOW_SIZE, "delta": round(delta_b, 3), "direction": direction_b},
            }

            if _same_shift(direction_a, direction_b):
                if str(freshness.get("state") or "unknown") in {"fresh", "aging"}:
                    base.update({
                        "state": "confirmed_shift",
                        "direction": direction_b,
                        "confidence": "high" if freshness.get("state") == "fresh" else "medium",
                    })
                else:
                    base.update({
                        "state": "candidate_shift",
                        "direction": direction_b,
                        "confidence": "low",
                        "confirmation_blocked_by_freshness": True,
                    })
                return base

            if direction_a in {"improving", "declining"} and direction_b in {"improving", "declining"} and direction_a != direction_b:
                base.update({
                    "state": "volatile_noise",
                    "direction": "mixed",
                    "confidence": "medium" if freshness.get("state") in {"fresh", "aging"} else "low",
                })
                return base

            if direction_b in {"improving", "declining"}:
                base.update({
                    "state": "candidate_shift",
                    "direction": direction_b,
                    "confidence": "medium" if freshness.get("state") == "fresh" else "low",
                })
                return base

            base.update({
                "state": "stable_baseline",
                "direction": "stable",
                "confidence": "medium" if freshness.get("state") in {"fresh", "aging"} else "low",
            })
            return base

        # Six to eight comparable cycles can surface a candidate, but cannot
        # confirm a regime. This is intentionally conservative.
        block = usable[-MIN_CANDIDATE_CYCLES:]
        baseline = [_score(row.get("outcome")) for row in block[:WINDOW_SIZE]]
        recent = [_score(row.get("outcome")) for row in block[-WINDOW_SIZE:]]
        delta = mean(recent) - mean(baseline)
        direction = _direction(delta)
        base["windows"] = {
            "baseline": {"cycles": WINDOW_SIZE, "mean": round(mean(baseline), 3)},
            "candidate": {"cycles": WINDOW_SIZE, "delta": round(delta, 3), "direction": direction},
        }
        if direction in {"improving", "declining"}:
            base.update({
                "state": "candidate_shift",
                "direction": direction,
                "confidence": "medium" if freshness.get("state") == "fresh" else "low",
            })
        else:
            base.update({
                "state": "stable_baseline",
                "direction": "stable",
                "confidence": "low",
            })
        return base

    @classmethod
    def snapshot(cls, deep_history: Mapping[str, Any] | None, *, now=None) -> dict[str, Any]:
        history = dict(deep_history or {})
        by_focus: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in list(history.get("timeline") or []):
            if not isinstance(raw, Mapping):
                continue
            focus = str(raw.get("focus") or "").strip().casefold()[:40]
            if not focus:
                continue
            by_focus[focus].append(dict(raw))

        rows = {
            focus: cls._focus_snapshot(focus, cycles, now=now)
            for focus, cycles in by_focus.items()
        }
        priority = {
            "confirmed_shift": 5,
            "contradictory": 4,
            "candidate_shift": 3,
            "volatile_noise": 2,
            "stable_baseline": 1,
            "insufficient_evidence": 0,
        }
        dominant = max(
            rows.values(),
            key=lambda row: (priority.get(str(row.get("state") or ""), -1), int(row.get("comparable_cycles") or 0), str(row.get("focus") or "")),
            default=None,
        )
        return {
            "schema": "bco_player_regime_change_v35",
            "minimum_candidate_cycles": MIN_CANDIDATE_CYCLES,
            "minimum_confirmed_cycles": MIN_CONFIRMED_CYCLES,
            "window_size": WINDOW_SIZE,
            "shift_delta": SHIFT_DELTA,
            "by_focus": rows,
            "dominant": dict(dominant) if isinstance(dominant, Mapping) else None,
            "truth_contract": {
                "one_session_can_change_regime": False,
                "shift_does_not_identify_cause": True,
                "cause_remains_unknown_without_separate_evidence": True,
                "external_meta_change_not_inferred": True,
                "stale_evidence_cannot_confirm_current_shift": True,
                "vod_contradiction_cannot_confirm_shift": True,
                "explicit_outcome_authoritative": True,
                "association_not_causation": True,
                "causal_claims": False,
                "client_premium_authority": False,
            },
        }

    @staticmethod
    def focus_row(snapshot: Mapping[str, Any] | None, focus: str) -> dict[str, Any]:
        rows = (snapshot or {}).get("by_focus") if isinstance((snapshot or {}).get("by_focus"), Mapping) else {}
        row = rows.get(str(focus or "").strip().casefold()) if isinstance(rows, Mapping) else None
        if isinstance(row, Mapping):
            return dict(row)
        return {
            "focus": str(focus or "").strip().casefold()[:40],
            "state": "insufficient_evidence",
            "direction": "unknown",
            "confidence": "unknown",
            "comparable_cycles": 0,
            "cause": "unknown",
            "cause_claim": False,
        }

    @classmethod
    def strategy_guard(cls, snapshot: Mapping[str, Any] | None, strategy_class: str, focus: str) -> dict[str, Any]:
        row = cls.focus_row(snapshot, focus)
        state = str(row.get("state") or "insufficient_evidence")
        direction = str(row.get("direction") or "unknown")
        strategy = str(strategy_class or "")
        adjustment = 0
        reason = "neutral"

        if strategy == "regression_intercept":
            if state == "confirmed_shift" and direction == "declining":
                adjustment, reason = 3, "confirmed_declining_shift"
            elif state == "candidate_shift" and direction == "declining":
                adjustment, reason = -3, "candidate_not_confirmed"
            elif state in {"volatile_noise", "stable_baseline", "contradictory", "insufficient_evidence"}:
                adjustment, reason = -6, f"{state}_guards_regression_reaction"
        elif strategy == "stability_validation":
            if state == "confirmed_shift" and direction == "improving":
                adjustment, reason = 3, "confirmed_improving_shift"
            elif state == "candidate_shift" and direction == "improving":
                adjustment, reason = -3, "candidate_not_confirmed"
            elif state in {"volatile_noise", "stable_baseline", "contradictory", "insufficient_evidence"}:
                adjustment, reason = -6, f"{state}_guards_improvement_reaction"
        elif strategy == "contradiction_resolution" and state == "contradictory":
            adjustment, reason = 3, "cross_source_contradiction_present"
        elif strategy == "consistency_build" and state == "stable_baseline":
            adjustment, reason = 2, "stable_baseline_supports_consistency"

        return {
            "state": state,
            "direction": direction,
            "confidence": str(row.get("confidence") or "unknown"),
            "cause": "unknown",
            "cause_claim": False,
            "priority_adjustment": adjustment,
            "reason": reason,
            "one_session_can_change_regime": False,
        }
