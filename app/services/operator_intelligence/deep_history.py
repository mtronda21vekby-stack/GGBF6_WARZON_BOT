# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Mapping

from app.services.operator_intelligence.service import MISSION_EVENT_TYPE
from app.services.vod.mission_evidence import EVENT_TYPE as MISSION_EVIDENCE_EVENT_TYPE

PREMIUM_MAX_CYCLES = 36
MIN_FOCUS_COMPARISON_CYCLES = 4


def _at(row: Mapping[str, Any]) -> str:
    return str(row.get("at") or row.get("created_at") or "")[:64]


def _score(outcome: str) -> float:
    return {"clean": 1.0, "mixed": 0.0, "failed": -1.0}.get(outcome, 0.0)


class PremiumDeepHistoryService:
    """Long-horizon operator analysis for server-authorized Premium only.

    Authorization is deliberately NOT implemented here. Callers must resolve
    `bco_premium` through the server entitlement service before invoking this
    class. This service never trusts browser/profile Premium flags.
    """

    def __init__(self, store: Any):
        self.store = store

    def _rows(self, chat_id: int) -> list[dict[str, Any]]:
        fn = getattr(self.store, "list_progression_events", None)
        if not callable(fn):
            return []
        try:
            rows = fn(int(chat_id), 100)
        except TypeError:
            rows = fn(int(chat_id))
        except Exception:
            return []
        return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        rows = self._rows(int(chat_id))
        completed = [
            row for row in rows
            if str(row.get("type") or "") == MISSION_EVENT_TYPE
            and str(row.get("status") or "").casefold() == "completed"
            and str(row.get("outcome") or "").casefold() in {"clean", "mixed", "failed"}
        ]
        completed.sort(key=_at)
        completed = completed[-PREMIUM_MAX_CYCLES:]

        evidence_by_mission: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if str(row.get("type") or "") != MISSION_EVIDENCE_EVENT_TYPE:
                continue
            mission_id = str(row.get("mission_id") or "").strip()
            if mission_id:
                evidence_by_mission[mission_id].append(row)

        focus_cycles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        contradictions = 0
        vod_cycles = 0
        clean_total = mixed_total = failed_total = 0
        timeline: list[dict[str, Any]] = []

        for row in completed:
            mission_id = str(row.get("mission_id") or "").strip()[:64]
            focus = str(row.get("focus") or "unknown").strip().casefold()[:40]
            outcome = str(row.get("outcome") or "").casefold()
            evidence = evidence_by_mission.get(mission_id, [])
            high_risk = any(
                str(item.get("classification") or "") == "mission_relevant_evidence_high"
                for item in evidence
            )
            contradiction = outcome == "clean" and high_risk
            contradictions += int(contradiction)
            vod_cycles += int(bool(evidence))
            clean_total += int(outcome == "clean")
            mixed_total += int(outcome == "mixed")
            failed_total += int(outcome == "failed")

            item = {
                "mission_id": mission_id,
                "focus": focus,
                "outcome": outcome,
                "at": _at(row),
                "vod_correlated": bool(evidence),
                "contradiction": contradiction,
            }
            focus_cycles[focus].append(item)
            timeline.append(item)

        comparisons: list[dict[str, Any]] = []
        for focus, cycles in focus_cycles.items():
            if len(cycles) < MIN_FOCUS_COMPARISON_CYCLES:
                continue
            values = [_score(str(item.get("outcome") or "")) for item in cycles]
            midpoint = max(2, len(values) // 2)
            prior = values[:midpoint]
            recent = values[midpoint:]
            if len(recent) < 2:
                continue
            delta = mean(recent) - mean(prior)
            direction = "stable"
            if delta >= 0.45:
                direction = "improving"
            elif delta <= -0.45:
                direction = "declining"
            focus_contradictions = sum(1 for item in cycles if item.get("contradiction"))
            comparisons.append({
                "focus": focus,
                "cycles": len(cycles),
                "prior_cycles": len(prior),
                "recent_cycles": len(recent),
                "direction": direction,
                "contradictions": focus_contradictions,
                "confidence": "medium" if focus_contradictions else ("high" if len(cycles) >= 8 else "medium"),
                "latest_at": str(cycles[-1].get("at") or "")[:64],
                "causal_claim": False,
            })

        comparisons.sort(key=lambda item: (-int(item["cycles"]), str(item["focus"])))
        strongest = next((item for item in comparisons if item["direction"] == "improving"), None)
        regression = next((item for item in comparisons if item["direction"] == "declining"), None)

        return {
            "schema": "bco_premium_deep_history_v29",
            "premium_scope": "server_authorized_bco_premium",
            "horizon": {
                "max_cycles": PREMIUM_MAX_CYCLES,
                "observed_cycles": len(completed),
                "focus_comparison_minimum": MIN_FOCUS_COMPARISON_CYCLES,
            },
            "outcomes": {
                "clean": clean_total,
                "mixed": mixed_total,
                "failed": failed_total,
            },
            "evidence": {
                "vod_correlated_cycles": vod_cycles,
                "contradictions": contradictions,
                "contradiction_detected": contradictions > 0,
            },
            "focus_comparisons": comparisons[:8],
            "signals": {
                "strongest_improvement": strongest,
                "regression_watch": regression,
            },
            "truth_contract": {
                "association_not_causation": True,
                "causal_claims": False,
                "explicit_outcome_authoritative": True,
                "sampled_frame_vod_does_not_rewrite_outcome": True,
                "client_premium_authority": False,
            },
            "timeline": timeline[-12:],
        }
