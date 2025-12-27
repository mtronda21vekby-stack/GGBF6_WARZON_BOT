# -*- coding: utf-8 -*-
from typing import Dict, Any

PERSONA_HINT = {"spicy": "Дерзко 😈", "chill": "Спокойно 😌", "pro": "Профи 🎯"}
VERB_HINT = {"short": "Коротко", "normal": "Норм", "talkative": "Подробно"}
GAME_HINT = {"auto": "AUTO", "warzone": "Warzone", "bf6": "BF6", "bo7": "BO7"}

def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"

def main_text(p: Dict[str, Any], ai_enabled: bool, model: str) -> str:
    g = p.get("game", "auto")
    mode = p.get("mode", "chat")
    return (
        f"🧠 FPS Coach Bot | 🎮 {GAME_HINT.get(g, g)} | 🔁 {mode.upper()} | 🤖 AI {'ON' if ai_enabled else 'OFF'}\n\n"
        "Напиши ситуацию/смерть — разберу.\n"
        "Или жми кнопки снизу 👇"
    )

def help_text() -> str:
    return (
        "🆘 Помощь\n\n"
        "Команды:\n"
        "• /start — старт\n"
        "• /menu — меню\n"
        "• /status — статус\n"
        "• /profile — профиль\n"
        "• /daily — задание дня\n"
        "• /reset — сброс\n\n"
        "Кнопки снизу = то же самое."
    )

def status_text(model: str, data_dir: str, ai_enabled: bool) -> str:
    return (
        "📡 Статус:\n"
        f"• AI: {'ON' if ai_enabled else 'OFF'}\n"
        f"• Model: {model}\n"
        f"• Data dir: {data_dir}\n"
    )

def profile_text(p: Dict[str, Any]) -> str:
    return (
        "👤 Профиль:\n"
        f"• game: {p.get('game','auto')}\n"
        f"• mode: {p.get('mode','chat')}\n"
        f"• persona: {p.get('persona','spicy')} ({PERSONA_HINT.get(p.get('persona','spicy'),'')})\n"
        f"• verbosity: {p.get('verbosity','normal')} ({VERB_HINT.get(p.get('verbosity','normal'),'')})\n"
        f"• memory: {_badge(p.get('memory','on')=='on')}\n"
        f"• speed: {p.get('speed','normal')}\n"
        f"• ui: {p.get('ui','show')}\n"
        f"• player_level: {p.get('player_level','normal')}\n"
        f"• wz_device: {p.get('wz_device','pad')} | wz_tier: {p.get('wz_tier','normal')}\n"
        f"• bf6_device: {p.get('bf6_device','pad')} | bf6_tier: {p.get('bf6_tier','normal')}\n"
        f"• bo7_device: {p.get('bo7_device','pad')} | bo7_tier: {p.get('bo7_tier','normal')}\n"
    )