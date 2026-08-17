# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.ui.command_console import ConsoleView, home_view
from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card
from app.ui.quickbar import _webapp_url


def _clean(value: Any, fallback: str = "—", limit: int = 180) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or fallback)[:limit]


def _callback(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text[:64], "callback_data": data[:64]}
    if style:
        button["style"] = style
    return button


def _markup(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    raw = {"inline_keyboard": [row for row in rows if row]}
    return decorate_reply_markup(raw) or raw


def home_view_v19(profile: Mapping[str, Any] | None) -> ConsoleView:
    """Add the v19 mission surface without rewriting the stable v16 console."""
    base = home_view(profile)
    markup = deepcopy(base.reply_markup)
    rows = markup.get("inline_keyboard")
    if not isinstance(rows, list):
        rows = []
        markup["inline_keyboard"] = rows
    if not any(
        isinstance(button, Mapping) and button.get("callback_data") == "bco:mission"
        for row in rows
        if isinstance(row, list)
        for button in row
    ):
        rows.insert(0, [_callback("◈ ADAPTIVE MISSION CONTROL", "bco:mission", "primary")])

    text = base.text.replace(
        "Выбери модуль.",
        "Adaptive Mission Control формирует одну активную измеримую задачу из памяти, VOD и прогресса.\n\nВыбери модуль.",
    )
    return ConsoleView(text=text, reply_markup=decorate_reply_markup(markup) or markup)


def mission_view(snapshot: Mapping[str, Any] | None, *, note: str = "") -> ConsoleView:
    data = dict(snapshot or {})
    state = dict(data.get("state") or {})
    mission = dict(data.get("mission") or {})
    history = dict(data.get("history") or {})
    enabled = bool(data.get("enabled", True))

    mission_id = _clean(mission.get("id"), "", 48)
    status = _clean(mission.get("status"), "candidate", 16).upper()
    focus = _clean(mission.get("focus"), "positioning", 32).upper()
    title = _clean(mission.get("title"), "CALIBRATION PROTOCOL", 80)
    objective = _clean(mission.get("objective"), "Собрать первый надёжный игровой сигнал.", 500)
    why = _clean(mission.get("why"), "Недостаточно доказательств; используется безопасная калибровка.", 700)
    match_rule = _clean(mission.get("match_rule"), "Одна задача на матч. Не менять правило в середине попытки.", 500)
    metric = _clean(mission.get("success_metric"), "После матча отправить результат одним сообщением.", 500)

    readiness = max(0, min(100, int(state.get("readiness") or 0)))
    momentum = max(0, min(100, int(state.get("momentum") or 0)))
    risk = max(0, min(100, int(state.get("risk") or 0)))
    confidence = max(0, min(100, int(state.get("confidence_pct") or 0)))
    mode = _clean(state.get("mode"), "CALIBRATE", 24).upper()
    risk_level = _clean(state.get("risk_level"), "MODERATE", 24).upper()

    lines = [
        "ADAPTIVE MISSION CONTROL // V19",
        "",
        f"STATE — {mode}",
        f"MISSION — {status}",
        f"FOCUS — {focus}",
        "",
        f"READINESS {readiness} · MOMENTUM {momentum}",
        f"CONFIDENCE {confidence} · RISK {risk} / {risk_level}",
        "",
        f"{title}",
        objective,
        "",
        "WHY THIS MISSION:",
        why,
        "",
        "MATCH RULE:",
        match_rule,
        "",
        "SUCCESS METRIC:",
        metric,
    ]

    protocol = list(mission.get("protocol") or [])
    if protocol:
        lines.extend(["", f"PROTOCOL // {int(mission.get('duration_min') or 0)} MIN"])
        for item in protocol[:3]:
            if not isinstance(item, Mapping):
                continue
            phase = _clean(item.get("phase"), "PHASE", 24).upper()
            minutes = max(0, int(item.get("minutes") or 0))
            action = _clean(item.get("action"), "", 260)
            lines.append(f"• {phase} · {minutes}m — {action}")

    evidence = list(mission.get("evidence") or [])
    if evidence:
        lines.extend(["", "EVIDENCE:"])
        for item in evidence[:3]:
            if not isinstance(item, Mapping):
                continue
            label = _clean(item.get("label"), "signal", 160)
            weight = item.get("weight")
            suffix = f" · W{weight}" if weight not in (None, "") else ""
            lines.append(f"• {label}{suffix}")

    lines.extend([
        "",
        f"CYCLES — accepted {int(history.get('accepted') or 0)} · completed {int(history.get('completed') or 0)}",
    ])
    if note:
        lines.extend(["", _clean(note, "", 500)])
    if not enabled:
        lines.extend(["", "MISSION CONTROL отключён runtime-флагом. Чтение доступно; изменения заблокированы."])

    rows: list[list[dict[str, Any]]] = []
    if enabled and mission_id and status == "CANDIDATE":
        rows.append([_callback("✓ ACCEPT MISSION", f"bco:m:a:{mission_id}", "success")])
    elif enabled and mission_id and status == "ACTIVE":
        rows.append([
            _callback("CLEAN", f"bco:m:c:clean:{mission_id}", "success"),
            _callback("MIXED", f"bco:m:c:mixed:{mission_id}", "primary"),
            _callback("FAILED", f"bco:m:c:failed:{mission_id}", "danger"),
        ])

    webapp_url = _webapp_url()
    if webapp_url:
        rows.append([{
            "text": "🛰 OPEN VISUAL MISSION CONTROL",
            "web_app": {"url": webapp_url},
            "style": "primary",
        }])
    rows.extend([
        [_callback("↻ RE-EVALUATE", "bco:m:r", "primary"), _callback("🧠 AI BRIEF", "bco:ai", "primary")],
        [_callback("‹ COMMAND CONSOLE", "bco:home")],
    ])
    return ConsoleView(
        text=tactical_card("\n".join(lines), channel="MISSION CONTROL"),
        reply_markup=_markup(rows),
    )
