# -*- coding: utf-8 -*-
from typing import List, Dict
from app.state import ensure_profile, USER_MEMORY, update_memory

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

SYSTEM = (
    "Ты FPS-коуч. Русский язык. Без токсичности.\n"
    "Запрещено: читы/хаки/обход античита.\n"
    "Формат:\n"
    "🎯 Диагноз\n"
    "✅ Сейчас (2 строки)\n"
    "🧪 Дрилл (1 короткий)\n"
    "😈 Мотивация\n"
)

def _fallback(text: str) -> str:
    return (
        "🎯 Диагноз\n"
        "Похоже на позиционку/тайминг.\n\n"
        "✅ Сейчас\n"
        "Сейчас — стоп репик, выйди с другого угла.\n"
        "Дальше — играй от инфо (звук/пинг), потом пик.\n\n"
        "🧪 Дрилл\n"
        "5 минут: после каждого файта 1 фраза «почему умер».\n\n"
        "😈 Мотивация\n"
        "Не магия. Привычка. 😈"
    )

def brain_reply(chat_id: int, user_text: str, ai_engine) -> str:
    p = ensure_profile(chat_id)
    game = p.get("game", "auto")
    persona = p.get("persona", "spicy")
    verb = p.get("verbosity", "normal")
    mode = p.get("mode", "chat")

    # память
    update_memory(chat_id, "user", user_text, max_turns=10)

    if not ai_engine.enabled:
        out = _fallback(user_text)
        update_memory(chat_id, "assistant", out, max_turns=10)
        return out

    msgs: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "system", "content": f"Игра: {game}. Стиль: {persona}. Длина: {verb}. Режим: {mode}."},
    ]
    if p.get("memory") == "on":
        msgs.extend(USER_MEMORY.get(chat_id, [])[-18:])

    msgs.append({"role": "user", "content": user_text})

    out = ai_engine.chat(msgs, max_tokens=450 if verb != "talkative" else 700)
    out = (out or "").strip() or _fallback(user_text)
    update_memory(chat_id, "assistant", out, max_turns=10)
    return out
