# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.operator_intelligence import OperatorIntelligenceService


_ALLOWED_CLAIMS = {
    "verified_fact",
    "high_confidence_player_pattern",
    "weak_pattern",
    "hypothesis",
    "unknown",
}


@dataclass(frozen=True)
class OperatorContextProjector:
    """Project the full Operator Twin into a bounded prompt-safe context.

    Internal evidence weights and scoring mechanics never cross this boundary.
    v28 exposes only bounded longitudinal interpretation with an explicit
    association-not-causation contract and contradiction telemetry.
    """

    max_claims: int = 8
    max_evidence_per_claim: int = 2

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    def _claim(self, domain: str, raw: Mapping[str, Any]) -> dict[str, Any]:
        claim_class = self._text(raw.get("claim_class") or "unknown", 48)
        if claim_class not in _ALLOWED_CLAIMS:
            claim_class = "unknown"
        evidence: list[dict[str, Any]] = []
        for item in list(raw.get("evidence") or [])[: self.max_evidence_per_claim]:
            if not isinstance(item, Mapping):
                continue
            evidence.append({
                "source": self._text(item.get("source"), 48),
                "fact_class": self._text(item.get("fact_class"), 48),
                "direction": self._text(item.get("direction"), 24),
                "label": self._text(item.get("label"), 180),
                "at": self._text(item.get("at"), 64),
            })
        return {
            "domain": self._text(domain, 40),
            "assessment": self._text(raw.get("assessment"), 40) or "unknown",
            "claim_class": claim_class,
            "confidence": self._text(raw.get("confidence"), 20) or "unknown",
            "evidence_count": max(0, min(999, int(raw.get("evidence_count") or 0))),
            "source_count": max(0, min(99, int(raw.get("source_count") or 0))),
            "recency_days": raw.get("recency_days") if isinstance(raw.get("recency_days"), int) else None,
            "trend": self._text(raw.get("trend"), 24) or "unknown",
            "uncertainty": self._text(raw.get("uncertainty"), 280),
            "evidence": evidence,
        }

    def _mission_evidence(self, raw: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            return {}
        signals: list[dict[str, Any]] = []
        for item in list(raw.get("signals") or [])[:6]:
            if not isinstance(item, Mapping):
                continue
            label = self._text(item.get("label"), 180)
            if not label:
                continue
            signals.append({
                "kind": self._text(item.get("kind"), 24),
                "label": label,
                "category": self._text(item.get("category"), 32) or "unknown",
                "confidence": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None,
                "timestamp": self._text(item.get("timestamp"), 32),
            })
        return {
            "classification": self._text(raw.get("classification"), 64),
            "confidence": self._text(raw.get("confidence"), 20) or "unknown",
            "clips": max(0, min(99, int(raw.get("clips") or 0))),
            "evidence_count": max(0, min(999, int(raw.get("evidence_count") or 0))),
            "sampled_frames": max(0, min(9999, int(raw.get("sampled_frames") or 0))),
            "source": self._text(raw.get("source"), 48),
            "latest_at": self._text(raw.get("latest_at"), 64),
            "does_not_complete_mission": True,
            "signals": signals,
        }

    def _longitudinal(self, raw: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            return {}
        return {
            "schema": self._text(raw.get("schema"), 64) or "bco_longitudinal_operator_v28",
            "minimum_cycles": max(3, min(12, int(raw.get("minimum_cycles") or 3))),
            "completed_cycles": max(0, min(99, int(raw.get("completed_cycles") or 0))),
            "directional_ready": bool(raw.get("directional_ready", False)),
            "trend": self._text(raw.get("trend"), 24) or "unknown",
            "volatility": self._text(raw.get("volatility"), 24) or "unknown",
            "confidence": self._text(raw.get("confidence"), 24) or "unknown",
            "contradictions": max(0, min(99, int(raw.get("contradictions") or 0))),
            "contradiction_detected": bool(raw.get("contradiction_detected", False)),
            "vod_correlated_cycles": max(0, min(99, int(raw.get("vod_correlated_cycles") or 0))),
            "dominant_focus": self._text(raw.get("dominant_focus"), 40) or "unknown",
            "association_rule": "association_not_causation",
            "causal_claims": False,
            "single_session_proves_improvement": False,
            "interpretation": self._text(raw.get("interpretation"), 500),
        }

    def project(self, snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
        data = dict(snapshot or {})
        operator = data.get("operator") if isinstance(data.get("operator"), Mapping) else {}
        dimensions = operator.get("dimensions") if isinstance(operator.get("dimensions"), Mapping) else {}

        claims: list[dict[str, Any]] = []
        unknown_dimensions: list[str] = []
        priority = {
            "limiting_signal": 0,
            "strength_signal": 1,
            "mixed_signal": 2,
            "neutral_observation": 3,
            "unknown": 4,
        }
        for domain, raw in dimensions.items():
            if not isinstance(raw, Mapping):
                continue
            claim = self._claim(str(domain), raw)
            if claim["claim_class"] == "unknown":
                unknown_dimensions.append(claim["domain"])
                continue
            claims.append(claim)
        claims.sort(key=lambda item: (
            priority.get(str(item.get("assessment")), 9),
            -int(item.get("evidence_count") or 0),
            str(item.get("domain") or ""),
        ))
        claims = claims[: max(1, min(12, int(self.max_claims or 8)))]

        mission_raw = data.get("mission") if isinstance(data.get("mission"), Mapping) else {}
        mission = {
            "id": self._text(mission_raw.get("id"), 64),
            "status": self._text(mission_raw.get("status"), 24),
            "focus": self._text(mission_raw.get("focus"), 40),
            "title": self._text(mission_raw.get("title"), 140),
            "objective": self._text(mission_raw.get("objective"), 500),
            "success_condition": self._text(mission_raw.get("success_condition"), 500),
            "confidence": self._text(mission_raw.get("confidence"), 20),
            "calibration": bool(mission_raw.get("calibration", False)),
        }
        mission = {key: value for key, value in mission.items() if value not in ("", None, False)}

        session_raw = data.get("session") if isinstance(data.get("session"), Mapping) else {}
        review_raw = session_raw.get("last_review") if isinstance(session_raw.get("last_review"), Mapping) else {}
        last_review = {
            "focus": self._text(review_raw.get("focus"), 40),
            "outcome": self._text(review_raw.get("outcome"), 24),
            "at": self._text(review_raw.get("at"), 64),
        }
        last_review = {key: value for key, value in last_review.items() if value}
        mission_evidence = self._mission_evidence(
            session_raw.get("mission_evidence") if isinstance(session_raw.get("mission_evidence"), Mapping) else None
        )
        longitudinal = self._longitudinal(
            data.get("longitudinal") if isinstance(data.get("longitudinal"), Mapping) else None
        )

        truth = operator.get("truth_model") if isinstance(operator.get("truth_model"), Mapping) else {}
        truth_summary = {
            "verified_facts": max(0, int(truth.get("verified_facts") or 0)),
            "high_confidence_patterns": max(0, int(truth.get("high_confidence_patterns") or 0)),
            "weak_patterns": max(0, int(truth.get("weak_patterns") or 0)),
            "hypotheses": max(0, int(truth.get("hypotheses") or 0)),
            "unknown_dimensions": max(0, int(truth.get("unknown_dimensions") or len(unknown_dimensions))),
        }

        return {
            "schema": "bco_operator_context_v28",
            "truth_contract": "never_promote_inference; unknown_remains_unknown; mission_evidence_does_not_complete; association_not_causation",
            "state": {
                "readiness": self._text(operator.get("readiness"), 32) or "UNKNOWN",
                "risk": self._text(operator.get("risk"), 32) or "UNKNOWN",
                "confidence": self._text(operator.get("confidence"), 32) or "UNKNOWN",
                "session_momentum": self._text(operator.get("session_momentum"), 32) or "UNKNOWN",
            },
            "claims": claims,
            "unknown_dimensions": unknown_dimensions[:12],
            "truth_summary": truth_summary,
            "mission": mission,
            "longitudinal": longitudinal,
            "session": {
                "phase": self._text(session_raw.get("phase"), 40) or "PRE_SESSION",
                "last_review": last_review,
                "mission_evidence": mission_evidence,
            },
        }


@dataclass
class OperatorContextService:
    store: Any
    profiles: Any
    operator_enabled: bool = True
    missions_enabled: bool = True

    def context(self, chat_id: int) -> dict[str, Any]:
        snapshot = OperatorIntelligenceService(
            store=self.store,
            profiles=self.profiles,
            operator_enabled=self.operator_enabled,
            missions_enabled=self.missions_enabled,
        ).snapshot(int(chat_id))
        return OperatorContextProjector().project(snapshot)
