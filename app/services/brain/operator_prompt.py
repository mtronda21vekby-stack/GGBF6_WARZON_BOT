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
    claims = list(raw.get("claims") or [])[:8]
    unknown = [_clean(x, 40) for x in list(raw.get("unknown_dimensions") or [])[:12] if _clean(x, 40)]

    lines = [
        f"schema={_clean(raw.get('schema'), 64) or 'bco_operator_context_v26'}",
        "truth_contract=never promote inference; unknown remains unknown",
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
    return "\n".join(lines)[:7000]
