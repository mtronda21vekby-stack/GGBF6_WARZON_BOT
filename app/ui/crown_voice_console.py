# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Mapping

from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card


def _clean(value: Any, fallback: str, limit: int = 32) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or fallback)[:limit]


def _callback(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text[:64], "callback_data": data[:64]}
    if style:
        button["style"] = style
    return button


def _active(label: str, active: bool, data: str, *, danger: bool = False) -> dict[str, Any]:
    prefix = "✓ " if active else ""
    style = ("danger" if danger else "success") if active else ("danger" if danger else "primary")
    return _callback(prefix + label, data, style)


def crown_voice_view(profile: Mapping[str, Any] | None) -> Any:
    from app.ui.command_console import ConsoleView

    source = dict(profile or {})
    role = _clean(source.get("voice"), "TEAMMATE").upper()
    identity = _clean(source.get("voice_identity"), "female").casefold()
    if identity not in {"female", "male"}:
        identity = "female"
    timbre = _clean(source.get("tts_voice"), "marin").casefold()
    mode = _clean(source.get("tts_mode"), "auto").casefold()

    identity_label = "FEMALE" if identity == "female" else "MALE"
    engine_label = timbre.upper()
    mode_label = {
        "off": "OFF",
        "on_demand": "ON-DEMAND",
        "auto": "AUTO",
    }.get(mode, "AUTO")

    body = (
        "CROWN VOICE // LIVE CONTROL\n\n"
        f"IDENTITY — {identity_label}\n"
        f"TIMBRE — {engine_label}\n"
        f"DELIVERY — {role}\n"
        f"OUTPUT — {mode_label}\n\n"
        "FEMALE и MALE используют один Intelligence Core, одну память и один профиль игрока. "
        "Меняется только голосовая идентичность и подача.\n\n"
        "FEMALE — MARIN: взрослый, спокойный, естественный женский профиль.\n"
        "MALE — CEDAR: собранный, естественный мужской профиль."
    )

    rows = [
        [
            _active("♀ FEMALE", identity == "female", "bco:set:voiceid:female"),
            _active("♂ MALE", identity == "male", "bco:set:voiceid:male"),
        ],
        [
            _active("TEAMMATE", role == "TEAMMATE", "bco:set:voice:teammate"),
            _active("COACH", role == "COACH", "bco:set:voice:coach"),
        ],
        [
            _active("AUTO", mode == "auto", "bco:set:ttsmode:auto"),
            _active("ON-DEMAND", mode == "on_demand", "bco:set:ttsmode:on_demand"),
            _active("OFF", mode == "off", "bco:set:ttsmode:off", danger=True),
        ],
        [
            _callback("⚙ SYSTEM", "bco:system"),
            _callback("⌂ HOME", "bco:home", "primary"),
        ],
    ]
    raw = {"inline_keyboard": rows}
    markup = decorate_reply_markup(raw) or raw
    return ConsoleView(text=tactical_card(body, channel="CROWN VOICE"), reply_markup=markup)


def inject_home_voice_button(view: Any, profile: Mapping[str, Any] | None) -> Any:
    """Expose CROWN VOICE on the actual AAA inline COMMAND CONSOLE surface."""
    from app.ui.command_console import ConsoleView

    source = dict(profile or {})
    identity = str(source.get("voice_identity") or "female").strip().casefold()
    label = "♀ VOICE" if identity != "male" else "♂ VOICE"
    markup = dict(getattr(view, "reply_markup", {}) or {})
    rows = [list(row) for row in (markup.get("inline_keyboard") or [])]

    button = {"text": label, "callback_data": "bco:voice", "style": "primary"}
    insert_at = max(0, len(rows) - 2)
    rows.insert(insert_at, [button])
    markup["inline_keyboard"] = rows
    return ConsoleView(text=view.text, reply_markup=decorate_reply_markup(markup) or markup)
