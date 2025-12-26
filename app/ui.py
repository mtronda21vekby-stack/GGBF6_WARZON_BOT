# app/ui.py
# -*- coding: utf-8 -*-

from app.state import ensure_profile


def _btn(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


def main_menu_markup(chat_id: int) -> dict:
    """
    Главное меню: только верхние тумблеры + Zombies + кнопка "Ещё".
    Нижние кнопки (тренировка/профиль/настройки/...) будут ТОЛЬКО в "Ещё".
    """
    p = ensure_profile(chat_id)

    game = (p.get("game") or "auto").upper()
    persona = p.get("persona") or "spicy"
    verbosity = p.get("verbosity") or "normal"
    memory = "✅" if p.get("memory", "on") == "on" else "❌"
    ai = "ON" if p.get("ai", "on") == "on" else "OFF"
    mode = (p.get("mode") or "chat").upper()
    lightning = "ВКЛ" if p.get("lightning", "off") == "on" else "ВЫКЛ"

    return {
        "inline_keyboard": [
            [_btn(f"🎮 Игра: {game}", "set:game"), _btn(f"🎭 Стиль: {persona}", "set:persona")],
            [_btn(f"💬 Ответ: {verbosity}", "set:verbosity"), _btn(f"{memory} Память", "toggle:memory")],
            [_btn(f"🔁 Режим: {mode}", "set:mode"), _btn(f"🤖 ИИ: {ai}", "toggle:ai")],
            [_btn(f"⚡ Молния: {lightning}", "toggle:lightning"), _btn("🧟 Zombies", "zombies:home")],
            [_btn("📦 Ещё", "ui:more")],
        ]
    }


def more_menu_markup(chat_id: int) -> dict:
    """
    Второй экран меню (скрытые кнопки).
    """
    return {
        "inline_keyboard": [
            [_btn("💪 Тренировка", "more:training"), _btn("📊 Профиль", "more:profile")],
            [_btn("⚙️ Настройки", "more:settings"), _btn("🎯 Задание дня", "more:daily")],
            [_btn("🧽 Очистить память", "more:clear_memory"), _btn("🧨 Сбросить всё", "more:reset_all")],
            [_btn("⬅️ Назад", "ui:back")],
        ]
    }
