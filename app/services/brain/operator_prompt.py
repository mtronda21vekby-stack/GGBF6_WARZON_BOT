# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping


_CLAIM_LANGUAGE = {
    "verified_fact": "may be treated as an observed/reported fact within its stated scope",
    "high_confidence_player_pattern": "may be described as a strong recurring player pattern, not an absolute trait",
    "weak_pattern": "must be phrased tentatively and must not be stated as certainty",
    "hypothesis": "is only a hypothesis; use it to ask/measure, not to diagnose",
    "unknown": "must remain unknown; do not fill the gap from model intuition",
}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def render_operator_context(player_context: Mapping[str, Any] | None) -> str:
    root = dict(player_context or {})
    raw = root.get("operator_context")
    if not isinstance(raw, Mapping):
        return "Operator Twin context unavailable for this request. Do not infer missing operator traits."

    state = raw.get("state") if isinstance(raw.get("state"), Mapping) else {}
    session = raw.get("session") if isinstance(raw.get("session"), Mapping) else {}
    mission = raw.get("mission") if isinstance(raw.get("mission"), Mapping) else {}
    orchestrator = mission.get("orchestrator") if isinstance(mission.get("orchestrator"), Mapping) else {}
    mission_evidence = session.get("mission_evidence") if isinstance(session.get("mission_evidence"), Mapping) else {}
    claims = list(raw.get("claims") or [])[:8]
    unknown = [_clean(x, 40) for x in list(raw.get("unknown_dimensions") or [])[:12] if _clean(x, 40)]

    lines = [
        f"schema={_clean(raw.get('schema'), 64) or 'bco_operator_context_v28'}",
        "truth_contract=never promote inference; unknown remains unknown; sampled-frame mission evidence never completes a mission; mission stage moves only from explicit CLEAN/MIXED/FAILED reports; training stage is not a player trait",
        (
            "operator_state="
            f"readiness:{_clean(state.get('readiness'), 32) or 'UNKNOWN'}, "
            f"risk:{_clean(state.get('risk'), 32) or 'UNKNOWN'}, "
            f"confidence:{_clean(state.get('confidence'), 32) or 'UNKNOWN'}, "
            f"momentum:{_clean(state.get('session_momentum'), 32) or 'UNKNOWN'}"
        ),
        f"session_phase={_clean(session.get('phase'), 40) or 'PRE_SESSION'}",
    ]

    if mission:
        lines.extend([
            "current_mission:",
            f"- status={_clean(mission.get('status'), 24) or 'candidate'}",
            f"- focus={_clean(mission.get('focus'), 40) or 'unknown'}",
            f"- title={_clean(mission.get('title'), 140) or 'unknown'}",
            f"- objective={_clean(mission.get('objective'), 500) or 'unknown'}",
            f"- success_condition={_clean(mission.get('success_condition'), 500) or 'unknown'}",
            f"- calibration={bool(mission.get('calibration', False))}",
        ])
        if orchestrator or mission.get("training_stage"):
            lines.extend([
                "mission_orchestrator:",
                f"- stage={_clean(mission.get('training_stage') or orchestrator.get('stage'), 32) or 'CALIBRATION'}",
                f"- stage_label={_clean(mission.get('stage_label') or orchestrator.get('stage_label'), 80)}",
                f"- stage_success_condition={_clean(mission.get('stage_success_condition') or orchestrator.get('stage_success_condition'), 500)}",
                f"- next_stage_if_passed={_clean(orchestrator.get('next_stage_if_passed'), 32)}",
                f"- recalibration_required={bool(orchestrator.get('recalibration_required', False))}",
                "- transition_authority=explicit_operator_report_only",
                "- rule=VOD, inferred performance, hidden scores and a report without CLEAN/MIXED/FAILED cannot advance the training stage",
                "- rule=one bad match does not reset MAINTENANCE; stage movement is training-state control, not proof of player trait or cause",
            ])

    if mission_evidence:
        lines.extend([
            "mission_sampled_frame_evidence:",
            f"- classification={_clean(mission_evidence.get('classification'), 64) or 'unknown'}",
            f"- confidence={_clean(mission_evidence.get('confidence'), 20) or 'unknown'}",
            f"- clips={int(mission_evidence.get('clips') or 0)}; evidence_count={int(mission_evidence.get('evidence_count') or 0)}; sampled_frames={int(mission_evidence.get('sampled_frames') or 0)}",
            f"- source={_clean(mission_evidence.get('source'), 48) or 'vision_sampled_frames'}",
            "- rule=this evidence may inform the current mission analysis, but must never be described as continuous-video truth or as an automatic CLEAN/MIXED/FAILED mission result",
        ])
        for signal in list(mission_evidence.get("signals") or [])[:4]:
            if not isinstance(signal, Mapping):
                continue
            lines.append(
                "  sampled_signal: "
                f"category={_clean(signal.get('category'), 32) or 'unknown'}; "
                f"confidence={signal.get('confidence')}; timestamp={_clean(signal.get('timestamp'), 32)}; "
                f"label={_clean(signal.get('label'), 180)}"
            )

    if claims:
        lines.append("calibrated_claims:")
        for item in claims:
            if not isinstance(item, Mapping):
                continue
            cls = _clean(item.get("claim_class"), 48) or "unknown"
            language = _CLAIM_LANGUAGE.get(cls, _CLAIM_LANGUAGE["unknown"])
            lines.append(
                "- "
                f"domain={_clean(item.get('domain'), 40)}; "
                f"assessment={_clean(item.get('assessment'), 40)}; "
                f"claim_class={cls}; confidence={_clean(item.get('confidence'), 20) or 'unknown'}; "
                f"evidence_count={int(item.get('evidence_count') or 0)}; trend={_clean(item.get('trend'), 24) or 'unknown'}; "
                f"language_rule={language}; uncertainty={_clean(item.get('uncertainty'), 280)}"
            )
            for evidence in list(item.get("evidence") or [])[:2]:
                if not isinstance(evidence, Mapping):
                    continue
                lines.append(
                    "  evidence: "
                    f"source={_clean(evidence.get('source'), 48)}; "
                    f"fact_class={_clean(evidence.get('fact_class'), 48)}; "
                    f"direction={_clean(evidence.get('direction'), 24)}; "
                    f"label={_clean(evidence.get('label'), 180)}"
                )
    else:
        lines.append("calibrated_claims=none")

    lines.append("unknown_dimensions=" + (", ".join(unknown) if unknown else "none explicitly listed"))
    review = session.get("last_review") if isinstance(session.get("last_review"), Mapping) else {}
    if review:
        lines.append(
            "last_session_review="
            f"focus:{_clean(review.get('focus'), 40)}, outcome:{_clean(review.get('outcome'), 24)}, at:{_clean(review.get('at'), 64)}"
        )
    return "\n".join(lines)[:8000]
