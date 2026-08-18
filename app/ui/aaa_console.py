# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.i18n import normalize_locale
from app.ui.command_console import ConsoleView
from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card
from app.ui.quickbar import _webapp_url


def _locale(profile: Mapping[str, Any] | None) -> str:
    p = dict(profile or {})
    return normalize_locale(p.get("language_override") or p.get("language") or "en")


def _clean(value: Any, fallback: str = "—", limit: int = 96) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or fallback)[:limit]


def _button(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"text": text[:64], "callback_data": data[:64]}
    if style:
        item["style"] = style
    return item


def _webapp(text: str) -> dict[str, Any] | None:
    url = _webapp_url()
    if not url:
        return None
    return {"text": text[:64], "web_app": {"url": url}, "style": "primary"}


def _markup(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    raw = {"inline_keyboard": [row for row in rows if row]}
    return decorate_reply_markup(raw) or raw


def _view(channel: str, body: str, rows: list[list[dict[str, Any]]]) -> ConsoleView:
    return ConsoleView(text=tactical_card(body, channel=channel), reply_markup=_markup(rows))


def aaa_home_view(profile: Mapping[str, Any] | None, snapshot: Mapping[str, Any] | None) -> ConsoleView:
    p = dict(profile or {})
    s = dict(snapshot or {})
    op = dict(s.get("operator") or {})
    mission = dict(s.get("mission") or {})
    locale = _locale(p)
    game = _clean(p.get("game"), "Warzone", 24).upper()
    brain = _clean(p.get("difficulty"), "Normal", 16).upper()
    mode = _clean(p.get("voice"), "TEAMMATE", 16).upper()
    readiness = _clean(op.get("readiness"), "CALIBRATING", 24).upper()
    mission_title = _clean(mission.get("title"), "CALIBRATING", 72)

    if locale == "ru":
        body = (
            "CROWN // READY\n\n"
            "INTELLIGENCE — ONLINE\n"
            f"PLAYER BRAIN — {readiness}\n"
            f"МИССИЯ — {mission_title}\n\n"
            f"{game} · {brain} · {mode}\n\n"
            "BLACK CROWN готов к сессии. WAR ROOM показывает только то, что важно сейчас; полный функционал доступен в модулях и Mini App."
        )
        rows = [
            [_button("WAR ROOM", "bco:warroom", "primary"), _button("ОПЕРАТОР", "bco:profile", "success")],
            [_button("ГОЛОС", "bco:voice", "primary"), _button("ВСЕ МОДУЛИ", "bco:modules")],
        ]
        app = _webapp("ОТКРЫТЬ BLACK CROWN")
        if app: rows.append([app])
        rows.append([_button("ОБНОВИТЬ", "bco:home", "primary"), _button("ЗАКРЫТЬ", "bco:close")])
        return _view("CROWN", body, rows)

    body = (
        "CROWN // READY\n\n"
        "INTELLIGENCE — ONLINE\n"
        f"PLAYER BRAIN — {readiness}\n"
        f"MISSION — {mission_title}\n\n"
        f"{game} · {brain} · {mode}\n\n"
        "BLACK CROWN is ready for the session. WAR ROOM surfaces only what matters now; every capability remains available in Modules and the Mini App."
    )
    rows = [
        [_button("WAR ROOM", "bco:warroom", "primary"), _button("OPERATOR", "bco:profile", "success")],
        [_button("VOICE", "bco:voice", "primary"), _button("ALL MODULES", "bco:modules")],
    ]
    app = _webapp("OPEN BLACK CROWN")
    if app: rows.append([app])
    rows.append([_button("REFRESH", "bco:home", "primary"), _button("CLOSE", "bco:close")])
    return _view("CROWN", body, rows)


def war_room_view(profile: Mapping[str, Any] | None, snapshot: Mapping[str, Any] | None) -> ConsoleView:
    p = dict(profile or {})
    s = dict(snapshot or {})
    op = dict(s.get("operator") or {})
    mission = dict(s.get("mission") or {})
    session = dict(s.get("session") or {})
    locale = _locale(p)
    game = _clean(p.get("game"), "Warzone", 24).upper()
    phase = _clean(session.get("phase"), "PRE_SESSION", 24).upper()
    readiness = _clean(op.get("readiness"), "CALIBRATING", 24).upper()
    risk = _clean(op.get("risk"), "UNKNOWN", 24).upper()
    confidence = _clean(op.get("confidence"), "UNKNOWN", 24).upper()
    title = _clean(mission.get("title"), "CALIBRATING", 72)
    objective = _clean(mission.get("objective"), "Collecting enough evidence for a measurable objective.", 220)
    success = _clean(mission.get("success_condition"), "Not enough evidence yet.", 180)

    if locale == "ru":
        body = (
            f"WAR ROOM // {phase}\n\n"
            f"ИГРА — {game}\n"
            f"ОПЕРАТОР — {readiness}\n"
            f"РИСК — {risk}\n"
            f"УВЕРЕННОСТЬ — {confidence}\n\n"
            f"ТЕКУЩАЯ МИССИЯ\n{title}\n\n"
            f"ЦЕЛЬ\n{objective}\n\n"
            f"УСЛОВИЕ УСПЕХА\n{success}\n\n"
            "CROWN INTEL — синхронизирован. Слабые данные остаются CALIBRATING; предположение не выдаётся за факт."
        )
        rows = [
            [_button("МИССИЯ", "bco:profile", "success"), _button("AI СВОДКА", "bco:ai", "primary")],
            [_button("ТРЕНИРОВКА", "bco:training"), _button("VOD РАЗБОР", "bco:vod")],
        ]
        app = _webapp("ПОЛНЫЙ WAR ROOM")
        if app: rows.append([app])
        rows.append([_button("НАЗАД", "bco:home")])
        return _view("WAR ROOM", body, rows)

    body = (
        f"WAR ROOM // {phase}\n\n"
        f"WORLD — {game}\n"
        f"OPERATOR — {readiness}\n"
        f"RISK — {risk}\n"
        f"CONFIDENCE — {confidence}\n\n"
        f"CURRENT MISSION\n{title}\n\n"
        f"OBJECTIVE\n{objective}\n\n"
        f"SUCCESS CONDITION\n{success}\n\n"
        "CROWN INTEL — synchronized. Weak evidence remains CALIBRATING; inference is never presented as verified fact."
    )
    rows = [
        [_button("MISSION", "bco:profile", "success"), _button("AI BRIEF", "bco:ai", "primary")],
        [_button("TRAINING", "bco:training"), _button("VOD LAB", "bco:vod")],
    ]
    app = _webapp("FULL WAR ROOM")
    if app: rows.append([app])
    rows.append([_button("BACK", "bco:home")])
    return _view("WAR ROOM", body, rows)


def modules_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    locale = _locale(profile)
    if locale == "ru":
        body = (
            "ВСЕ СИСТЕМЫ\n\n"
            "Полный функционал BLACK CROWN. Основной экран остаётся спокойным; здесь доступны все специализированные модули без потери возможностей."
        )
        rows = [
            [_button("AI СВОДКА", "bco:ai", "primary"), _button("ТРЕНИРОВКА", "bco:training", "success")],
            [_button("ИГРА", "bco:world"), _button("VOD РАЗБОР", "bco:vod")],
            [_button("ЗОМБИ", "bco:zombies", "danger"), _button("ОПЕРАТОР", "bco:profile")],
            [_button("ПРЕМИУМ", "bco:premium", "success"), _button("СИСТЕМА", "bco:system")],
            [_button("ГОЛОС", "bco:voice", "primary"), _button("НАЗАД", "bco:home")],
        ]
        return _view("MODULES", body, rows)

    body = (
        "ALL SYSTEMS\n\n"
        "The complete BLACK CROWN capability set. The primary surface stays calm; every specialist module remains available here."
    )
    rows = [
        [_button("AI BRIEF", "bco:ai", "primary"), _button("TRAINING", "bco:training", "success")],
        [_button("WORLD", "bco:world"), _button("VOD LAB", "bco:vod")],
        [_button("ZOMBIES", "bco:zombies", "danger"), _button("OPERATOR", "bco:profile")],
        [_button("PREMIUM", "bco:premium", "success"), _button("SYSTEM", "bco:system")],
        [_button("VOICE", "bco:voice", "primary"), _button("BACK", "bco:home")],
    ]
    return _view("MODULES", body, rows)
