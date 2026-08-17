# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.ui.command_console import ConsoleView
from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card


def _button(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"text": text[:64], "callback_data": data[:64]}
    if style:
        item["style"] = style
    return item


def _markup(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    raw = {"inline_keyboard": [row for row in rows if row]}
    return decorate_reply_markup(raw) or raw


def _signal_line(item: Mapping[str, Any]) -> str:
    domain = str(item.get("domain") or "unknown").replace("_", " ").upper()
    confidence = str(item.get("confidence") or "unknown").upper()
    count = int(item.get("evidence_count") or 0)
    trend = str(item.get("trend") or "unknown").upper()
    return f"• {domain} — {confidence} · evidence {count} · {trend}"


def operator_view(snapshot: Mapping[str, Any] | None, *, note: str = "") -> ConsoleView:
    data = dict(snapshot or {})
    operator = dict(data.get("operator") or {})
    mission = dict(data.get("mission") or {})
    session = dict(data.get("session") or {})
    weaknesses = list(operator.get("weakness_signals") or [])[:3]

    readiness = str(operator.get("readiness") or "UNKNOWN")
    risk = str(operator.get("risk") or "UNKNOWN")
    confidence = str(operator.get("confidence") or "UNKNOWN")
    momentum = str(operator.get("session_momentum") or "UNKNOWN")
    phase = str(session.get("phase") or "PRE_SESSION")
    mission_title = str(mission.get("title") or "NO MISSION")
    focus = str(mission.get("focus") or "unknown").replace("_", " ")
    status = str(mission.get("status") or "candidate").upper()
    success = str(mission.get("success_condition") or "")
    basis = str(mission.get("basis") or "")

    signal_block = "\n".join(_signal_line(x) for x in weaknesses) if weaknesses else (
        "• Нет подтверждённой слабости. Unknown остаётся unknown."
    )

    review = session.get("last_review") if isinstance(session.get("last_review"), Mapping) else None
    review_block = ""
    if phase == "POST_SESSION_REVIEW" and review:
        review_block = (
            "\n\nPOST-SESSION REVIEW:\n"
            f"• RESULT — {str(review.get('outcome') or 'reported').upper()}\n"
            f"• MEMORY UPDATE — {str(session.get('memory_update') or 'complete').upper()}"
        )

    note_block = f"\n\n{note[:300]}" if note else ""
    body = (
        "OPERATOR TWIN // EVIDENCE DOSSIER\n\n"
        "OPERATOR STATE:\n"
        f"• READINESS — {readiness}\n"
        f"• RISK — {risk}\n"
        f"• CONFIDENCE — {confidence}\n"
        f"• MOMENTUM — {momentum}\n"
        f"• SESSION — {phase}\n\n"
        "WEAKNESS SIGNALS:\n"
        f"{signal_block}\n\n"
        "CURRENT MISSION:\n"
        f"• {mission_title}\n"
        f"• FOCUS — {focus.upper()} · {status}\n"
        f"• SUCCESS — {success or 'collecting evidence'}\n\n"
        f"BASIS: {basis or 'No hidden score. Mission is calibrated from available evidence.'}"
        f"{review_block}{note_block}"
    )

    rows: list[list[dict[str, Any]]] = []
    mission_id = str(mission.get("id") or "")
    if mission_id and status == "CANDIDATE":
        rows.append([_button("▶ ACCEPT MISSION", f"bco:m:accept:{mission_id}", "success")])
    elif mission_id and status == "ACTIVE":
        rows.append([
            _button("✓ CLEAN", f"bco:m:complete:clean:{mission_id}", "success"),
            _button("≈ MIXED", f"bco:m:complete:mixed:{mission_id}", "primary"),
            _button("✕ FAILED", f"bco:m:complete:failed:{mission_id}", "danger"),
        ])
    rows.append([_button("↻ REFRESH", "bco:profile", "primary"), _button("⌂ HOME", "bco:home")])
    return ConsoleView(text=tactical_card(body, channel="OPERATOR TWIN"), reply_markup=_markup(rows))
