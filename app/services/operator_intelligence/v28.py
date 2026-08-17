# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Mapping

from app.services.operator_intelligence.service import MISSION_EVENT_TYPE
from app.services.operator_intelligence.v27 import OperatorIntelligenceService as _V27OperatorIntelligenceService
from app.services.vod.mission_evidence import EVENT_TYPE as MISSION_EVIDENCE_EVENT_TYPE

MIN_DIRECTIONAL_CYCLES = 3
MAX_HISTORY_CYCLES = 12
_OUTCOME_SCORE = {"clean": 1.0, "mixed": 0.0, "failed": -1.0}


def _at(row: Mapping[str, Any]) -> str:
    return str(row.get("at") or row.get("created_at") or "")[:64]


def _bounded_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return max(0.0, min(100.0, number))


class OperatorIntelligenceService(_V27OperatorIntelligenceService):
    """v28 Operator Twin with longitudinal, contradiction-aware intelligence.

    Explicit operator mission outcomes remain authoritative. Sampled-frame VOD
    evidence may corroborate or contradict a cycle, but never changes its
    outcome and never creates a causal claim.
    """

    def _longitudinal(self, chat_id: int) -> dict[str, Any]:
        rows = self._rows("list_progression_events", int(chat_id), 100)
        completed = [
            row for row in rows
            if str(row.get("type") or "") == MISSION_EVENT_TYPE
            and str(row.get("status") or "").casefold() == "completed"
            and str(row.get("outcome") or "").casefold() in _OUTCOME_SCORE
        ]
        completed.sort(key=_at)
        completed = completed[-MAX_HISTORY_CYCLES:]

        evidence_by_mission: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if str(row.get("type") or "") != MISSION_EVIDENCE_EVENT_TYPE:
                continue
            mission_id = str(row.get("mission_id") or "").strip()
            if mission_id:
                evidence_by_mission[mission_id].append(row)

        cycles: list[dict[str, Any]] = []
        contradictions = 0
        focus_counts: dict[str, int] = defaultdict(int)
        scores: list[float] = []
        metric_scores: list[float] = []
        vod_correlated_cycles = 0

        for row in completed:
            mission_id = str(row.get("mission_id") or "").strip()
            focus = str(row.get("focus") or "unknown").strip().casefold()[:40]
            outcome = str(row.get("outcome") or "").casefold()
            score = _OUTCOME_SCORE[outcome]
            scores.append(score)
            focus_counts[focus] += 1

            metrics = row.get("metrics") if isinstance(row.get("metrics"), Mapping) else {}
            mission_score = _bounded_float(metrics.get("mission_score"))
            if mission_score is not None:
                metric_scores.append(mission_score)

            evidence_rows = evidence_by_mission.get(mission_id, [])
            high_vod_risk = any(
                str(item.get("classification") or "") == "mission_relevant_evidence_high"
                for item in evidence_rows
            )
            if evidence_rows:
                vod_correlated_cycles += 1

            contradiction = bool(outcome == "clean" and high_vod_risk)
            if contradiction:
                contradictions += 1

            cycles.append({
                "mission_id": mission_id[:64],
                "focus": focus,
                "outcome": outcome,
                "mission_score": mission_score,
                "at": _at(row),
                "vod_correlated": bool(evidence_rows),
                "contradiction": contradiction,
            })

        count = len(cycles)
        directional_ready = count >= MIN_DIRECTIONAL_CYCLES
        trend = "unknown"
        if directional_ready:
            midpoint = max(1, count // 2)
            earlier = scores[:midpoint]
            later = scores[midpoint:]
            delta = mean(later) - mean(earlier) if later else 0.0
            if delta >= 0.5:
                trend = "improving"
            elif delta <= -0.5:
                trend = "declining"
            else:
                trend = "stable"

        volatility = "unknown"
        if directional_ready:
            spread = pstdev(scores) if len(scores) > 1 else 0.0
            if spread >= 0.8:
                volatility = "high"
            elif spread >= 0.45:
                volatility = "moderate"
            else:
                volatility = "low"

        if count == 0:
            confidence = "unknown"
        elif not directional_ready:
            confidence = "low"
        elif contradictions > 0:
            confidence = "medium"
        elif count >= 6 and vod_correlated_cycles >= 2:
            confidence = "high"
        else:
            confidence = "medium"

        dominant_focus = "unknown"
        if focus_counts:
            dominant_focus = max(focus_counts.items(), key=lambda item: (item[1], item[0]))[0]

        if not directional_ready:
            interpretation = (
                f"Нужно минимум {MIN_DIRECTIONAL_CYCLES} explicit mission outcomes; "
                "одна удачная или неудачная сессия не считается устойчивым трендом."
            )
        elif contradictions:
            interpretation = (
                "Есть противоречие между explicit outcome и sampled-frame evidence. "
                "Система сохраняет оба сигнала и снижает уверенность вместо выбора удобной версии."
            )
        else:
            interpretation = (
                "Направление основано на нескольких explicit mission cycles. "
                "Это longitudinal association, а не доказанная причинность."
            )

        return {
            "schema": "bco_longitudinal_operator_v28",
            "minimum_cycles": MIN_DIRECTIONAL_CYCLES,
            "window_cycles": MAX_HISTORY_CYCLES,
            "completed_cycles": count,
            "directional_ready": directional_ready,
            "trend": trend,
            "volatility": volatility,
            "confidence": confidence,
            "contradictions": contradictions,
            "contradiction_detected": contradictions > 0,
            "vod_correlated_cycles": vod_correlated_cycles,
            "dominant_focus": dominant_focus,
            "mean_mission_score": round(mean(metric_scores), 2) if metric_scores else None,
            "association_rule": "association_not_causation",
            "causal_claims": False,
            "single_session_proves_improvement": False,
            "interpretation": interpretation,
            "cycles": cycles[-6:],
        }

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        snapshot = super().snapshot(chat_id)
        longitudinal = self._longitudinal(int(chat_id))
        snapshot["longitudinal"] = longitudinal
        operator = snapshot.get("operator") if isinstance(snapshot.get("operator"), dict) else {}
        operator["longitudinal_trend"] = longitudinal.get("trend", "unknown")
        operator["longitudinal_confidence"] = longitudinal.get("confidence", "unknown")
        operator["contradiction_detected"] = longitudinal.get("contradiction_detected", False)
        operator["association_not_causation"] = True
        snapshot["operator"] = operator
        return snapshot
