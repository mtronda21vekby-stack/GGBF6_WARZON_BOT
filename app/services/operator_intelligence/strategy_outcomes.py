# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping

from app.services.operator_intelligence.service import MISSION_EVENT_TYPE

STRATEGY_EVENT_TYPE = "premium_strategy"
STRATEGY_SOURCE = "premium_adaptive_strategy_v31"
MAX_TRACKED_STRATEGIES = 12
MAX_MATCHED_CYCLES = 3


def _at(row: Mapping[str, Any]) -> str:
    return str(row.get("at") or row.get("created_at") or "")[:64]


def strategy_id(payload: Mapping[str, Any]) -> str:
    stable = {
        "strategy_class": str(payload.get("strategy_class") or ""),
        "focus": str(payload.get("focus") or ""),
        "objective": str(payload.get("objective") or ""),
        "success_condition": str(payload.get("success_condition") or ""),
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "stg_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class PremiumStrategyOutcomeService:
    """Evaluate whether later explicit mission outcomes support a prior strategy.

    Matching is temporal + focus-based only. It is deliberately associative:
    no strategy is allowed to claim it caused a later clean/failed mission.
    """

    def __init__(self, store: Any):
        self.store = store

    def _rows(self, chat_id: int) -> list[dict[str, Any]]:
        fn = getattr(self.store, "list_progression_events", None)
        if not callable(fn):
            return []
        try:
            rows = fn(int(chat_id), 120)
        except TypeError:
            rows = fn(int(chat_id))
        except Exception:
            return []
        return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]

    def record_issue(self, chat_id: int, strategy: Mapping[str, Any]) -> str:
        sid = strategy_id(strategy)
        rows = self._rows(int(chat_id))
        if any(str(row.get("type") or "") == STRATEGY_EVENT_TYPE and str(row.get("strategy_id") or "") == sid for row in rows):
            return sid
        fn = getattr(self.store, "add_progression_event", None)
        if callable(fn):
            try:
                fn(int(chat_id), {
                    "type": STRATEGY_EVENT_TYPE,
                    "status": "issued",
                    "strategy_id": sid,
                    "strategy_class": str(strategy.get("strategy_class") or "")[:40],
                    "focus": str(strategy.get("focus") or "")[:40],
                    "confidence": str(strategy.get("confidence") or "unknown")[:16],
                    "source": STRATEGY_SOURCE,
                })
            except Exception:
                pass
        return sid

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        rows = self._rows(int(chat_id))
        rows.sort(key=_at)
        issued = [row for row in rows if str(row.get("type") or "") == STRATEGY_EVENT_TYPE and str(row.get("status") or "") == "issued"][-MAX_TRACKED_STRATEGIES:]
        missions = [
            row for row in rows
            if str(row.get("type") or "") == MISSION_EVENT_TYPE
            and str(row.get("status") or "").casefold() == "completed"
            and str(row.get("outcome") or "").casefold() in {"clean", "mixed", "failed"}
        ]

        evaluations: list[dict[str, Any]] = []
        by_class: dict[str, list[str]] = defaultdict(list)
        for strategy in issued:
            issued_at = _at(strategy)
            focus = str(strategy.get("focus") or "").casefold()
            matched = [
                row for row in missions
                if _at(row) > issued_at and str(row.get("focus") or "").casefold() == focus
            ][:MAX_MATCHED_CYCLES]
            outcomes = [str(row.get("outcome") or "").casefold() for row in matched]
            clean = outcomes.count("clean")
            mixed = outcomes.count("mixed")
            failed = outcomes.count("failed")
            if len(outcomes) < 2:
                verdict = "insufficient_followup"
            elif clean >= 2 and failed == 0:
                verdict = "supported_association"
            elif failed >= 2:
                verdict = "unsupported_association"
            else:
                verdict = "mixed_association"
            strategy_class = str(strategy.get("strategy_class") or "calibration")[:40]
            by_class[strategy_class].append(verdict)
            evaluations.append({
                "strategy_id": str(strategy.get("strategy_id") or ""),
                "strategy_class": strategy_class,
                "focus": focus,
                "issued_at": issued_at,
                "matched_cycles": len(outcomes),
                "outcomes": {"clean": clean, "mixed": mixed, "failed": failed},
                "verdict": verdict,
                "causal_claim": False,
            })

        class_summary = {}
        for strategy_class, verdicts in by_class.items():
            class_summary[strategy_class] = {
                "evaluated": sum(v != "insufficient_followup" for v in verdicts),
                "supported": verdicts.count("supported_association"),
                "mixed": verdicts.count("mixed_association"),
                "unsupported": verdicts.count("unsupported_association"),
            }

        latest = evaluations[-1] if evaluations else None
        return {
            "schema": "bco_premium_strategy_outcomes_v31",
            "tracked_strategies": len(evaluations),
            "latest": latest,
            "by_strategy_class": class_summary,
            "evaluations": evaluations[-8:],
            "truth_contract": {
                "association_not_causation": True,
                "causal_claims": False,
                "explicit_outcome_authoritative": True,
                "strategy_effectiveness_is_associative": True,
                "client_premium_authority": False,
            },
        }
