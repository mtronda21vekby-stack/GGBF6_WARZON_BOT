# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

FRESH_MAX_DAYS = 7
AGING_MAX_DAYS = 21
AGING_SIGNAL_PRIORITY_ADJUSTMENT = -5
STALE_SIGNAL_PRIORITY_ADJUSTMENT = -15


def _parse_at(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


class EvidenceFreshnessPolicy:
    """Bound current relevance without rewriting historical truth.

    Freshness is a recency policy over server-persisted evidence timestamps.
    It never changes an explicit mission outcome, never turns stale evidence
    into false evidence, and never manufactures certainty when timestamps are
    absent or invalid.
    """

    @staticmethod
    def classify(at: Any, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        else:
            current = current.astimezone(timezone.utc)
        parsed = _parse_at(at)
        if parsed is None or parsed > current + timedelta(minutes=5):
            return {
                "state": "unknown",
                "age_days": None,
                "evidence_at": str(at or "")[:64] or None,
            }

        age_seconds = max(0.0, (current - parsed).total_seconds())
        age_days = int(age_seconds // 86400)
        if age_days <= FRESH_MAX_DAYS:
            state = "fresh"
        elif age_days <= AGING_MAX_DAYS:
            state = "aging"
        else:
            state = "stale"
        return {
            "state": state,
            "age_days": age_days,
            "evidence_at": parsed.isoformat(),
        }

    @staticmethod
    def signal_priority_adjustment(state: str) -> int:
        value = str(state or "unknown").casefold()
        if value == "aging":
            return AGING_SIGNAL_PRIORITY_ADJUSTMENT
        if value == "stale":
            return STALE_SIGNAL_PRIORITY_ADJUSTMENT
        return 0

    @staticmethod
    def decay_portfolio_adjustment(adjustment: int, state: str) -> int:
        """Decay an old associative prior toward neutral, never past neutral."""
        raw = max(-2, min(2, int(adjustment or 0)))
        value = str(state or "unknown").casefold()
        if value == "stale":
            return 0
        if value == "aging":
            if raw > 0:
                return raw - 1
            if raw < 0:
                return raw + 1
        return raw

    @classmethod
    def snapshot(
        cls,
        deep_history: Mapping[str, Any] | None,
        effectiveness: Mapping[str, Any] | None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        history = dict(deep_history or {})
        effective = dict(effectiveness or {})

        focuses: dict[str, dict[str, Any]] = {}
        for raw in list(history.get("focus_comparisons") or []):
            if not isinstance(raw, Mapping):
                continue
            focus = str(raw.get("focus") or "").strip().casefold()[:40]
            if not focus:
                continue
            row = cls.classify(raw.get("latest_at"), now=now)
            row["source"] = "explicit_mission_comparison"
            focuses[focus] = row

        strategy_classes: dict[str, dict[str, Any]] = {}
        by_class = effective.get("by_strategy_class") if isinstance(effective.get("by_strategy_class"), Mapping) else {}
        for raw_name, raw_stats in dict(by_class or {}).items():
            if not isinstance(raw_stats, Mapping):
                continue
            name = str(raw_name or "").strip()[:40]
            if not name:
                continue
            row = cls.classify(raw_stats.get("latest_evaluated_at"), now=now)
            row["source"] = "explicit_strategy_followup"
            strategy_classes[name] = row

        return {
            "schema": "bco_evidence_freshness_v34",
            "policy": {
                "fresh_max_days": FRESH_MAX_DAYS,
                "aging_max_days": AGING_MAX_DAYS,
                "aging_signal_priority_adjustment": AGING_SIGNAL_PRIORITY_ADJUSTMENT,
                "stale_signal_priority_adjustment": STALE_SIGNAL_PRIORITY_ADJUSTMENT,
            },
            "focuses": focuses,
            "strategy_classes": strategy_classes,
            "truth_contract": {
                "stale_is_not_false": True,
                "freshness_changes_current_relevance_only": True,
                "missing_timestamp_remains_unknown": True,
                "old_support_is_not_current_proof": True,
                "explicit_outcome_authoritative": True,
                "association_not_causation": True,
                "causal_claims": False,
                "client_premium_authority": False,
            },
        }

    @staticmethod
    def focus_row(snapshot: Mapping[str, Any] | None, focus: str) -> dict[str, Any]:
        rows = (snapshot or {}).get("focuses") if isinstance((snapshot or {}).get("focuses"), Mapping) else {}
        row = rows.get(str(focus or "").strip().casefold()) if isinstance(rows, Mapping) else None
        return dict(row) if isinstance(row, Mapping) else {"state": "unknown", "age_days": None, "evidence_at": None}

    @staticmethod
    def strategy_class_row(snapshot: Mapping[str, Any] | None, strategy_class: str) -> dict[str, Any]:
        rows = (snapshot or {}).get("strategy_classes") if isinstance((snapshot or {}).get("strategy_classes"), Mapping) else {}
        row = rows.get(str(strategy_class or "").strip()) if isinstance(rows, Mapping) else None
        return dict(row) if isinstance(row, Mapping) else {"state": "unknown", "age_days": None, "evidence_at": None}
