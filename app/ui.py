# -*- coding: utf-8 -*-
from typing import Dict, Any, List
from app.state import ensure_profile

PERSONA_HINT = {"spicy": "дерзко 😈", "chill": "спокойно 😌", "pro": "профи 🎯"}
VERB_HINT = {"short": "коротко", "normal": "норм", "talkative": "подробно"}
GAME_HINT = {"auto": "AUTO", "warzone": "Warzone", "bf6": "BF6", "bo7": "BO7"}

def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"

def main_text(chat_id: int, ai_enabled: bool, model: str) -> str:
    p = ensure_profile(chat_id)
    g = p.get("game", "auto")
    mode = p.get("mode", "chat")
    persona = p.get("persona", "spicy")
    verbosity = p.get("verbosity", "normal")
    mem = p.get("memory", "on") == "on"
    speed = p.get("speed", "normal")
    return (
        f"🌑 FPS Coach Bot | Brain v3\n"
        f"🎮 {GAME_HINT.get(g,g)} | 🔁 {mode.upper()} | 🤖 AI {'ON' if ai_enabled else 'OFF'}\n"
        f"🎭 {persona} ({PERSONA_HINT.get(persona,'')}) | 🗣 {verbosity} ({VERB_HINT.get(verbosity,'')})\n"
        f"🧠 Память {_badge(mem)} | ⚡ {'Молния' if speed=='lightning' else 'Обычный'}\n\n"
        "Напиши ситуацию/смерть — разберу.\n"
        "Для управления жми кнопки снизу 👇"
    )

def status_text(model: str, data_dir: str, ai_enabled: bool) -> str:
    return (
        "📡 Статус:\n"
        f"• AI: {'ON' if ai_enabled else 'OFF'}\n"
        f"• Model: {model}\n"
        f"• Data dir: {data_dir}\n"
    )

def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    return (
        "👤 Профиль:\n"
        f"• game: {p.get('game','auto')}\n"
        f"• mode: {p.get('mode','chat')}\n"
        f"• persona: {p.get('persona','spicy')} ({PERSONA_HINT.get(p.get('persona','spicy'),'')})\n"
        f"• verbosity: {p.get('verbosity','normal')} ({VERB_HINT.get(p.get('verbosity','normal'),'')})\n"
        f"• memory: {_badge(p.get('memory','on')=='on')}\n"
        f"• speed: {p.get('speed','normal')}\n"
        f"• player_level: {p.get('player_level','normal')}\n"
        f"• wz_device: {p.get('wz_device','pad')} | wz_tier: {p.get('wz_tier','normal')}\n"
        f"• bf6_device: {p.get('bf6_device','pad')} | bf6_tier: {p.get('bf6_tier','normal')} | bf6_class: {p.get('bf6_class','assault')}\n"
        f"• bo7_device: {p.get('bo7_device','pad')} | bo7_tier: {p.get('bo7_tier','normal')}\n"
    )

def help_text() -> str:
    return (
        "🆘 Помощь\n\n"
        "• /start или /menu — показать меню\n"
        "• /status — статус\n"
        "• /profile — профиль\n"
        "• /daily — задание дня\n"
        "• /reset — сброс\n\n"
        "Всё управление — кнопками снизу."
    )

# -------------------------
# Premium Reply Keyboard (нижняя)
# -------------------------

def reply_keyboard_main() -> Dict[str, Any]:
    # Главная клавиатура — супер удобная, без inline
    rows: List[List[str]] = [
        ["📋 Меню", "⚙️ Настройки", "🆘 Помощь"],
        ["🎮 Игра", "🎭 Стиль", "🗣 Ответ"],
        ["🧟 Zombies", "🎯 Задание дня", "🎬 VOD"],
        ["👤 Профиль", "📡 Статус"],
        ["🧠 Память", "⚡ Молния"],
        ["🧽 Очистить память", "🧨 Сброс"],
    ]
    return {
        "keyboard": [[{"text": b} for b in r] for r in rows],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
        "input_field_placeholder": "Напиши ситуацию или жми кнопки снизу…",
    }

def reply_keyboard_settings() -> Dict[str, Any]:
    rows: List[List[str]] = [
        ["🎮 Warzone настройки", "🟨 BF6 классы", "🎮 BO7 настройки"],
        ["⬅️ Назад в меню"],
    ]
    return {
        "keyboard": [[{"text": b} for b in r] for r in rows],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }

def reply_keyboard_wz_device() -> Dict[str, Any]:
    rows = [
        ["🎮 WZ: PS5/Xbox (Pad)", "🖥 WZ: PC (MnK)"],
        ["⬅️ Назад в настройки"],
    ]
    return {"keyboard": [[{"text": b} for b in r] for r in rows], "resize_keyboard": True, "is_persistent": True}

def reply_keyboard_bo7_device() -> Dict[str, Any]:
    rows = [
        ["🎮 BO7: PS5/Xbox (Pad)", "🖥 BO7: PC (MnK)"],
        ["⬅️ Назад в настройки"],
    ]
    return {"keyboard": [[{"text": b} for b in r] for r in rows], "resize_keyboard": True, "is_persistent": True}

def reply_keyboard_bf6_classes() -> Dict[str, Any]:
    rows = [
        ["🟥 Assault", "🟦 Engineer"],
        ["🟩 Support", "🟨 Recon"],
        ["🧠 BF6: Обычный", "😈 BF6: Demon", "🎯 BF6: Pro"],
        ["🎮 BF6: Pad", "🖥 BF6: MnK"],
        ["⬅️ Назад в настройки"],
    ]
    return {"keyboard": [[{"text": b} for b in r] for r in rows], "resize_keyboard": True, "is_persistent": True}
