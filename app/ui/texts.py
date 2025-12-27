# -*- coding: utf-8 -*-
from typing import Dict, Any

def main_text(profile: Dict[str, Any], ai_on: bool, model: str) -> str:
    return (
        "🧠 Brain v3 — Premium FPS Assistant\n\n"
        f"🎮 Игра: {profile.get('game')}\n"
        f"🎭 Стиль: {profile.get('persona')}\n"
        f"🗣 Ответ: {profile.get('verbosity')}\n"
        f"🔁 Режим: {profile.get('mode')}\n"
        f"😈 Уровень: {profile.get('player_level')}\n"
        f"🧠 Память: {profile.get('memory')}\n\n"
        f"🤖 OpenAI: {'ON' if ai_on else 'OFF'}  |  model={model}\n\n"
        "Напиши ситуацию: где умер / что не получается / что прокачать."
    )

def help_text() -> str:
    return (
        "🆘 Помощь\n\n"
        "• Пиши как в игре: карта, позиция, оружие, дистанция, кто первый увидел.\n"
        "• Кнопки снизу — это команды.\n"
        "• /start — старт\n"
        "• /menu — меню\n"
        "• /reset — сброс\n"
    )

def status_text(model: str, data_dir: str, ai_on: bool) -> str:
    return (
        "📡 Статус\n"
        f"• AI: {'ON' if ai_on else 'OFF'}\n"
        f"• Model: {model}\n"
        f"• Data: {data_dir}\n"
        "• Render: health endpoint /health\n"
    )

def profile_text(profile: Dict[str, Any]) -> str:
    lines = [f"👤 Профиль:"]
    for k in ("game","persona","verbosity","mode","player_level","memory","day"):
        lines.append(f"• {k}: {profile.get(k)}")
    return "\n".join(lines)