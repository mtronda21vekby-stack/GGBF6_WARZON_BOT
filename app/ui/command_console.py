# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.ui.native_buttons import decorate_reply_markup
from app.ui.presentation import tactical_card
from app.ui.quickbar import _webapp_url


CALLBACK_PREFIX = "bco:"


@dataclass(frozen=True)
class ConsoleView:
    text: str
    reply_markup: dict[str, Any]


def _clean(value: Any, fallback: str, limit: int = 32) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or fallback)[:limit]


def _profile(profile: Mapping[str, Any] | None) -> dict[str, str]:
    source = dict(profile or {})
    return {
        "game": _clean(source.get("game"), "Warzone"),
        "platform": _clean(source.get("platform"), "PC"),
        "input": _clean(source.get("input"), "Controller"),
        "difficulty": _clean(source.get("difficulty"), "Normal"),
        "voice": _clean(source.get("voice"), "TEAMMATE"),
        "role": _clean(source.get("role"), "Flex"),
        "bf6_class": _clean(source.get("bf6_class"), "Assault"),
        "zombies_map": _clean(source.get("zombies_map"), "Ashes"),
        "training_focus": _clean(source.get("training_focus"), "aim"),
    }


def _callback(text: str, data: str, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text[:64], "callback_data": data[:64]}
    if style:
        button["style"] = style
    return button


def _url(text: str, url: str, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text[:64], "url": url}
    if style:
        button["style"] = style
    return button


def _webapp_button() -> dict[str, Any] | None:
    url = _webapp_url()
    if not url:
        return None
    return {
        "text": "🛰 COMMAND CENTER",
        "web_app": {"url": url},
        "style": "primary",
    }


def _markup(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    cleaned = [row for row in rows if row]
    raw = {"inline_keyboard": cleaned}
    return decorate_reply_markup(raw) or raw


def _view(channel: str, body: str, rows: list[list[dict[str, Any]]]) -> ConsoleView:
    return ConsoleView(
        text=tactical_card(body, channel=channel),
        reply_markup=_markup(rows),
    )


def _active(label: str, active: bool, data: str, *, danger: bool = False) -> dict[str, Any]:
    prefix = "✓ " if active else ""
    if active:
        style = "danger" if danger else "success"
    else:
        style = "danger" if danger else "primary"
    return _callback(prefix + label, data, style)


def _footer(*, include_webapp: bool = True) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    webapp = _webapp_button() if include_webapp else None
    if webapp:
        rows.append([webapp])
    rows.append(
        [
            _callback("↻ REFRESH", "bco:home", "primary"),
            _callback("✕ CLOSE", "bco:close"),
        ]
    )
    return rows


def home_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    body = (
        "OPERATOR LINK // ONLINE\n\n"
        "CURRENT LOADOUT:\n"
        f"• WORLD — {p['game'].upper()}\n"
        f"• PLATFORM — {p['platform'].upper()} · {p['input'].upper()}\n"
        f"• CORE — {p['difficulty'].upper()} · {p['voice'].upper()}\n"
        f"• ROLE — {p['role'].upper()}\n\n"
        "Выбери модуль. Навигация работает внутри одной консоли — без серой клавиатуры и лишних сообщений."
    )
    rows = [
        [
            _callback("🧠 AI BRIEF", "bco:ai", "primary"),
            _callback("🎯 TRAINING", "bco:training", "success"),
        ],
        [
            _callback("🎮 WORLD", "bco:world", "primary"),
            _callback("🎬 VOD LAB", "bco:vod", "success"),
        ],
        [
            _callback("🧟 ZOMBIES", "bco:zombies", "danger"),
            _callback("📌 OPERATOR", "bco:profile", "primary"),
        ],
        [
            _callback("💎 PREMIUM", "bco:premium", "success"),
            _callback("⚙️ SYSTEM", "bco:system"),
        ],
    ]
    rows.extend(_footer())
    return _view("COMMAND CONSOLE", body, rows)


def world_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    game = p["game"].casefold()
    platform = p["platform"].casefold()
    input_name = p["input"].casefold()
    body = (
        "MISSION ENVIRONMENT\n\n"
        f"Active world: {p['game']}\n"
        f"Platform: {p['platform']}\n"
        f"Input: {p['input']}\n\n"
        "Изменение применяется сразу к AI, тренировкам, VOD и памяти игрока."
    )
    rows = [
        [
            _active("WARZONE", "warzone" in game, "bco:set:game:wz"),
            _active("BO7", "bo7" in game, "bco:set:game:bo7"),
            _active("BF6", "bf6" in game, "bco:set:game:bf6"),
        ],
        [
            _active("PC", platform == "pc", "bco:set:platform:pc"),
            _active("PS", "play" in platform, "bco:set:platform:ps"),
            _active("XBOX", "xbox" in platform, "bco:set:platform:xbox"),
        ],
        [
            _active("CONTROLLER", "controller" in input_name, "bco:set:input:controller"),
            _active("KBM", "kbm" in input_name, "bco:set:input:kbm"),
        ],
        [_callback("‹ COMMAND CONSOLE", "bco:home")],
    ]
    return _view("WORLD SELECT", body, rows)


def brain_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    mode = p["difficulty"].casefold()
    body = (
        "REASONING INTENSITY\n\n"
        f"Active core: {p['difficulty'].upper()}\n\n"
        "NORMAL — быстрые ответы.\n"
        "PRO — причинный разбор и trade-offs.\n"
        "DEMON — максимальная дисциплина и глубина без выдуманных фактов."
    )
    rows = [
        [
            _active("NORMAL", "normal" in mode, "bco:set:brain:normal"),
            _active("PRO", "pro" in mode, "bco:set:brain:pro"),
            _active("DEMON", "demon" in mode, "bco:set:brain:demon", danger=True),
        ],
        [_callback("‹ SYSTEM", "bco:system"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("INTELLIGENCE CORE", body, rows)


def voice_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    voice = p["voice"].casefold()
    body = (
        "DELIVERY PROFILE\n\n"
        f"Active voice: {p['voice'].upper()}\n\n"
        "TEAMMATE — коротко, быстро, как связь внутри отряда.\n"
        "COACH — глубже, строже и с измеримым следующим действием."
    )
    rows = [
        [
            _active("TEAMMATE", "team" in voice, "bco:set:voice:teammate"),
            _active("COACH", "coach" in voice or "коуч" in voice, "bco:set:voice:coach"),
        ],
        [_callback("‹ SYSTEM", "bco:system"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("VOICE MATRIX", body, rows)


def profile_view(profile: Mapping[str, Any] | None, stats: Mapping[str, Any] | None = None) -> ConsoleView:
    p = _profile(profile)
    memory = dict(stats or {})
    turns = memory.get("turns", "—")
    mistakes = memory.get("recurring_mistakes", "—")
    sessions = memory.get("training_sessions", "—")
    body = (
        "OPERATOR DOSSIER\n\n"
        "IDENTITY:\n"
        f"• WORLD — {p['game']}\n"
        f"• PLATFORM — {p['platform']} · {p['input']}\n"
        f"• ROLE — {p['role']}\n"
        f"• CORE — {p['difficulty']} · {p['voice']}\n\n"
        "PERSISTENT INTELLIGENCE:\n"
        f"• DIALOGUE TURNS — {turns}\n"
        f"• RECURRING MISTAKES — {mistakes}\n"
        f"• TRAINING SESSIONS — {sessions}"
    )
    rows = [
        [_callback("🎮 WORLD", "bco:world", "primary"), _callback("😈 CORE", "bco:brain", "danger")],
        [_callback("🎙 VOICE", "bco:voice", "primary"), _callback("⚙️ SYSTEM", "bco:system")],
        [_callback("‹ COMMAND CONSOLE", "bco:home")],
    ]
    return _view("OPERATOR PROFILE", body, rows)


def system_view(profile: Mapping[str, Any] | None, stats: Mapping[str, Any] | None = None) -> ConsoleView:
    p = _profile(profile)
    memory = dict(stats or {})
    backend = _clean(memory.get("backend"), "persistent", 24).upper()
    body = (
        "SYSTEM CONTROL\n\n"
        "RUNTIME:\n"
        f"• MEMORY — {backend}\n"
        f"• WORLD — {p['game'].upper()}\n"
        f"• CORE — {p['difficulty'].upper()}\n"
        f"• VOICE — {p['voice'].upper()}\n\n"
        "Критические действия остаются за отдельным подтверждением."
    )
    rows = [
        [_callback("🎮 WORLD", "bco:world", "primary"), _callback("😈 BRAIN MODE", "bco:brain", "danger")],
        [_callback("🎙 VOICE", "bco:voice", "primary"), _callback("📌 PROFILE", "bco:profile", "primary")],
        [_callback("📊 REFRESH STATUS", "bco:system", "success")],
        [_callback("‹ COMMAND CONSOLE", "bco:home")],
    ]
    rows.extend(_footer())
    return _view("SYSTEM", body, rows)


def ai_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    body = (
        "AI COMBAT BRIEF\n\n"
        f"Core: {p['difficulty']} · {p['voice']}\n"
        f"World: {p['game']} · {p['platform']} · {p['input']}\n\n"
        "Напиши следующим сообщением ситуацию одним блоком:\n"
        "• что произошло\n"
        "• где ты умер или потерял преимущество\n"
        "• чего хотел добиться\n\n"
        "Свободный текст сразу попадёт в Intelligence Core."
    )
    rows = [
        [_callback("😈 BRAIN MODE", "bco:brain", "danger"), _callback("🎙 VOICE", "bco:voice", "primary")],
        [_callback("🎯 TRAINING", "bco:training", "success"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("AI BRIEF", body, rows)


def training_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    focus = p["training_focus"].casefold()
    body = (
        "TRAINING PROTOCOL\n\n"
        f"World: {p['game']} · Input: {p['input']}\n"
        f"Current focus: {p['training_focus'].upper()}\n\n"
        "Выбери фокус, затем напиши длительность и проблему.\n"
        "Пример: «20 минут, постоянно теряю цель после первого выстрела»."
    )
    rows = [
        [
            _active("AIM", focus == "aim", "bco:set:focus:aim"),
            _active("MOVEMENT", focus == "movement", "bco:set:focus:movement"),
            _active("POSITION", focus == "position", "bco:set:focus:position"),
        ],
        [_callback("🧠 AI BRIEF", "bco:ai", "primary"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("TRAINING", body, rows)


def vod_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    body = (
        "VOD INTELLIGENCE LAB\n\n"
        f"World context: {p['game']} · {p['role']}\n\n"
        "Отправь видео прямо в чат — реальный VOD pipeline извлечёт ключевые кадры.\n"
        "Либо отправь таймкоды и описание решения текстом.\n\n"
        "Система не будет утверждать, что видела кадры, если пришёл только текст."
    )
    rows = [
        [_callback("🧠 AI BRIEF", "bco:ai", "primary"), _callback("📌 PROFILE", "bco:profile", "primary")],
        [_callback("⌂ HOME", "bco:home")],
    ]
    return _view("VOD LAB", body, rows)


def zombies_view(profile: Mapping[str, Any] | None) -> ConsoleView:
    p = _profile(profile)
    map_name = p["zombies_map"].casefold()
    body = (
        "ZOMBIES OPERATIONS\n\n"
        f"Active map: {p['zombies_map']}\n\n"
        "Выбери карту, затем спроси про маршрут, Pack-a-Punch, перки, босса или пасхалку.\n"
        "Ответ получит контекст выбранной карты автоматически."
    )
    rows = [
        [
            _active("ASHES", "ashes" in map_name, "bco:set:zmap:ashes", danger=True),
            _active("ASTRA", "astra" in map_name, "bco:set:zmap:astra", danger=True),
        ],
        [_callback("🎬 VOD LAB", "bco:vod", "success"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("ZOMBIES", body, rows)


def premium_view(
    status: Any = None,
    *,
    error: str = "",
    link_url: str = "",
    link_ttl_minutes: int | None = None,
    note: str = "",
) -> ConsoleView:
    linked = bool(getattr(status, "linked", False))
    premium = bool(getattr(status, "premium", False))
    entitlements = tuple(getattr(status, "entitlements", ()) or ())

    if error:
        state = "STATUS OFFLINE"
        detail = "Серверный entitlement сейчас не подтверждён. Остальные функции бота продолжают работать."
    elif premium:
        state = "PREMIUM ACTIVE"
        detail = "Authority: Supabase GAME · server entitlement."
    elif linked:
        state = "ACCOUNT LINKED · PREMIUM INACTIVE"
        detail = "Привязка подтверждена, но entitlement Premium отсутствует."
    else:
        state = "NOT LINKED"
        detail = "Свяжи Telegram с текущим аккаунтом BlackCrown. Привязка сама по себе не выдаёт Premium."

    lines = [
        "ACCOUNT AUTHORITY",
        "",
        f"STATE: {state}",
        detail,
    ]
    if entitlements:
        lines.extend(["", "ENTITLEMENTS:", *[f"• {item}" for item in entitlements[:8]]])
    if note:
        lines.extend(["", note])
    if link_url and link_ttl_minutes:
        lines.extend(["", f"Одноразовая ссылка активна примерно {link_ttl_minutes} мин."])

    rows: list[list[dict[str, Any]]] = []
    if link_url:
        rows.append([_url("🔗 OPEN BLACKCROWN", link_url, "primary")])
    elif not linked:
        rows.append([_callback("🔗 LINK ACCOUNT", "bco:p:link", "primary")])
    if linked:
        rows.append([_callback("🔓 UNLINK", "bco:p:unlink", "danger")])
    rows.extend(
        [
            [_callback("↻ VERIFY STATUS", "bco:premium", "success")],
            [_callback("‹ COMMAND CONSOLE", "bco:home")],
        ]
    )
    return _view("PREMIUM", "\n".join(lines), rows)


def premium_unlink_confirm_view() -> ConsoleView:
    body = (
        "ACCOUNT UNLINK\n\n"
        "Подтверди удаление связи между текущим Telegram и аккаунтом сайта.\n\n"
        "Покупки и entitlements не удаляются. Удаляется только identity link."
    )
    rows = [
        [_callback("⚠ CONFIRM UNLINK", "bco:p:confirm", "danger")],
        [_callback("CANCEL", "bco:premium"), _callback("⌂ HOME", "bco:home")],
    ]
    return _view("SECURITY", body, rows)
