# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any, Mapping

from app.i18n import normalize_locale

_RU_BUTTONS = {
    "🧠 AI BRIEF":"🧠 AI СВОДКА","🎯 TRAINING":"🎯 ТРЕНИРОВКА","🎮 WORLD":"🎮 ИГРА","🎬 VOD LAB":"🎬 VOD РАЗБОР",
    "🧟 ZOMBIES":"🧟 ЗОМБИ","📌 OPERATOR":"📌 ОПЕРАТОР","💎 PREMIUM":"💎 ПРЕМИУМ","⚙️ SYSTEM":"⚙️ СИСТЕМА",
    "🛰 COMMAND CENTER":"🛰 ЦЕНТР УПРАВЛЕНИЯ","↻ REFRESH":"↻ ОБНОВИТЬ","✕ CLOSE":"✕ ЗАКРЫТЬ","‹ COMMAND CONSOLE":"‹ КОНСОЛЬ",
    "⌂ HOME":"⌂ ГЛАВНАЯ","😈 BRAIN MODE":"😈 РЕЖИМ ИИ","🎙 VOICE":"🎙 ГОЛОС","📌 PROFILE":"📌 ПРОФИЛЬ",
    "📊 REFRESH STATUS":"📊 ОБНОВИТЬ СТАТУС","AIM":"ТОЧНОСТЬ","MOVEMENT":"ДВИЖЕНИЕ","POSITION":"ПОЗИЦИЯ",
    "CONTROLLER":"КОНТРОЛЛЕР","TEAMMATE":"ТИММЕЙТ","COACH":"КОУЧ","‹ SYSTEM":"‹ СИСТЕМА",
}
_EN_BUTTONS = {
    "🧠 AI СВОДКА":"🧠 AI BRIEF","🎯 ТРЕНИРОВКА":"🎯 TRAINING","🎮 ИГРА":"🎮 WORLD","🎬 VOD РАЗБОР":"🎬 VOD LAB",
    "🧟 ЗОМБИ":"🧟 ZOMBIES","📌 ОПЕРАТОР":"📌 OPERATOR","💎 ПРЕМИУМ":"💎 PREMIUM","⚙️ СИСТЕМА":"⚙️ SYSTEM",
    "🛰 ЦЕНТР УПРАВЛЕНИЯ":"🛰 COMMAND CENTER","↻ ОБНОВИТЬ":"↻ REFRESH","✕ ЗАКРЫТЬ":"✕ CLOSE","‹ КОНСОЛЬ":"‹ COMMAND CONSOLE",
    "⌂ ГЛАВНАЯ":"⌂ HOME","😈 РЕЖИМ ИИ":"😈 BRAIN MODE","🎙 ГОЛОС":"🎙 VOICE","📌 ПРОФИЛЬ":"📌 PROFILE",
    "📊 ОБНОВИТЬ СТАТУС":"📊 REFRESH STATUS","ТОЧНОСТЬ":"AIM","ДВИЖЕНИЕ":"MOVEMENT","ПОЗИЦИЯ":"POSITION",
    "КОНТРОЛЛЕР":"CONTROLLER","ТИММЕЙТ":"TEAMMATE","КОУЧ":"COACH","‹ СИСТЕМА":"‹ SYSTEM",
}
_RU_TEXT = {
    "OPERATOR LINK // ONLINE":"СВЯЗЬ С ОПЕРАТОРОМ // ОНЛАЙН","CURRENT LOADOUT:":"ТЕКУЩАЯ КОНФИГУРАЦИЯ:","WORLD —":"ИГРА —","PLATFORM —":"ПЛАТФОРМА —","CORE —":"ЯДРО —","ROLE —":"РОЛЬ —",
    "MISSION ENVIRONMENT":"БОЕВАЯ СРЕДА","Active world:":"Активная игра:","Platform:":"Платформа:","Input:":"Управление:",
    "REASONING INTENSITY":"ГЛУБИНА АНАЛИЗА","Active core:":"Активное ядро:","DELIVERY PROFILE":"ПРОФИЛЬ ВЗАИМОДЕЙСТВИЯ","Active voice:":"Активный режим:",
    "OPERATOR DOSSIER":"ДОСЬЕ ОПЕРАТОРА","IDENTITY:":"ПРОФИЛЬ:","PERSISTENT INTELLIGENCE:":"ПОСТОЯННАЯ ПАМЯТЬ:","DIALOGUE TURNS —":"ДИАЛОГОВ —","RECURRING MISTAKES —":"ПОВТОРЯЮЩИХСЯ ОШИБОК —","TRAINING SESSIONS —":"ТРЕНИРОВОЧНЫХ СЕССИЙ —",
    "SYSTEM CONTROL":"УПРАВЛЕНИЕ СИСТЕМОЙ","RUNTIME:":"СОСТОЯНИЕ:","MEMORY —":"ПАМЯТЬ —","VOICE —":"РЕЖИМ —","AI COMBAT BRIEF":"БОЕВАЯ AI-СВОДКА",
    "TRAINING PROTOCOL":"ТРЕНИРОВОЧНЫЙ ПРОТОКОЛ","Current focus:":"Текущий фокус:","VOD INTELLIGENCE LAB":"ЛАБОРАТОРИЯ VOD-АНАЛИЗА","World context:":"Контекст игры:",
}
_EN_TEXT = {
    "Выбери модуль. Навигация работает внутри одной консоли — без серой клавиатуры и лишних сообщений.":"Choose a module. Navigation stays inside one console — no giant reply keyboard or message clutter.",
    "Изменение применяется сразу к AI, тренировкам, VOD и памяти игрока.":"Changes apply immediately to AI, training, VOD and player memory.",
    "NORMAL — быстрые ответы.":"NORMAL — fast useful intelligence.","PRO — причинный разбор и trade-offs.":"PRO — deeper analysis and trade-offs.","DEMON — максимальная дисциплина и глубина без выдуманных фактов.":"DEMON — maximum legitimate depth without invented facts.",
    "TEAMMATE — коротко, быстро, как связь внутри отряда.":"TEAMMATE — fast, concise and immediately actionable.","COACH — глубже, строже и с измеримым следующим действием.":"COACH — deeper analysis with a measurable next action.",
    "Критические действия остаются за отдельным подтверждением.":"Critical actions still require explicit confirmation.",
    "Напиши следующим сообщением ситуацию одним блоком:":"Describe the situation in your next message:","• что произошло":"• what happened","• где ты умер или потерял преимущество":"• where you died or lost the advantage","• чего хотел добиться":"• what you were trying to achieve","Свободный текст сразу попадёт в Intelligence Core.":"Free text goes directly to the Intelligence Core.",
    "Выбери фокус, затем напиши длительность и проблему.":"Choose a focus, then send the duration and problem.","Пример: «20 минут, постоянно теряю цель после первого выстрела».":"Example: “20 minutes, I keep losing the target after the first shot.”",
    "Отправь видео прямо в чат — реальный VOD pipeline извлечёт ключевые кадры.":"Send video directly in chat — the real VOD pipeline will extract key frames.","Либо отправь таймкоды и описание решения текстом.":"Or send timestamps and describe the decision in text.","Система не будет утверждать, что видела кадры, если пришёл только текст.":"The system will never claim it analyzed video pixels when only text was provided.",
}

_VIEW_NAMES = ("home_view","world_view","brain_view","voice_view","profile_view","system_view","ai_view","training_view","vod_view","zombies_view")


def _locale(profile: Mapping[str, Any] | None) -> str:
    p = dict(profile or {})
    return normalize_locale(p.get("language_override") or p.get("language") or "en")


def _translate_text(text: str, locale: str) -> str:
    mapping = _RU_TEXT if locale == "ru" else _EN_TEXT
    out = text
    for old, new in mapping.items():
        out = out.replace(old, new)
    return out


def _translate_markup(markup: dict[str, Any], locale: str) -> dict[str, Any]:
    mapping = _RU_BUTTONS if locale == "ru" else _EN_BUTTONS
    result = deepcopy(markup)
    rows = result.get("inline_keyboard") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, list):
            continue
        for button in row:
            if not isinstance(button, dict):
                continue
            label = str(button.get("text") or "")
            active = label.startswith("✓ ")
            raw = label[2:] if active else label
            translated = mapping.get(raw, raw)
            button["text"] = ("✓ " if active else "") + translated
    return result


def localize_view(view: Any, profile: Mapping[str, Any] | None) -> Any:
    locale = _locale(profile)
    text = _translate_text(str(view.text), locale)
    markup = _translate_markup(view.reply_markup, locale)
    try:
        return type(view)(text=text, reply_markup=markup)
    except Exception:
        return view


def _wrap(original):
    if getattr(original, "_bco_i18n_v41_wrapped", False):
        return original
    @wraps(original)
    def wrapped(*args, __original=original, **kwargs):
        profile = args[0] if args and isinstance(args[0], Mapping) else kwargs.get("profile")
        return localize_view(__original(*args, **kwargs), profile)
    wrapped._bco_i18n_v41_wrapped = True
    return wrapped


def install() -> None:
    import app.ui.command_console as cc
    wrapped_by_name = {}
    for name in _VIEW_NAMES:
        original = getattr(cc, name, None)
        if not callable(original):
            continue
        wrapped = _wrap(original)
        setattr(cc, name, wrapped)
        wrapped_by_name[name] = wrapped
    try:
        import app.services.telegram.command_console as controller
        for name, wrapped in wrapped_by_name.items():
            if hasattr(controller, name):
                setattr(controller, name, wrapped)
    except Exception:
        pass
    cc._bco_full_i18n_v41 = True
