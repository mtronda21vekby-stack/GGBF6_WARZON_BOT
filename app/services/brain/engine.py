# app/services/brain/engine.py
from __future__ import annotations

from dataclasses import dataclass

from app.services.brain.memory import InMemoryStore
from app.services.profiles.service import ProfileService
from app.config import Settings


@dataclass
class BrainReply:
    text: str


class BrainEngine:
    """
    Сейчас: умный “скелет” (без внешнего ИИ), но с профилем/памятью.
    Дальше сюда подключаем OpenAI (ключ только через ENV), не меняя роутер/кнопки.
    """

    def __init__(self, store: InMemoryStore, profiles: ProfileService, settings: Settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_text(self, user_id: int, text: str) -> BrainReply:
        p = self.profiles.get(user_id)

        # Быстрые команды/кнопки
        t = (text or "").strip()

        if t.lower() in ("/start", "меню", "📋 меню"):
            return BrainReply(self._welcome(p))

        # главный режим: разбор ситуации
        reply = self._coach_reply(p, t)
        self.store.add_turn(user_id, t, reply)
        return BrainReply(reply)

    def _welcome(self, p: dict) -> str:
        return (
            "FPS Coach Bot v3 | 🎮 AUTO | 🔁 CHAT | 🤖 AI ON\n\n"
            "Напиши ситуацию/смерть — разберём и сделаем план.\n"
            "Или жми кнопки снизу 👇"
        )

    def _coach_reply(self, p: dict, user_text: str) -> str:
        game = p.get("game", "AUTO")
        inp = p.get("input", "AUTO")
        diff = p.get("difficulty", "NORMAL")

        # Важно: BF6 — кнопки/настройки на EN (ты просил),
        # но остальной текст — RU (позже расширим).
        # Сейчас ответ “умный скелет”, чтобы бот не молчал.
        header = f"🎮 {game} | 🎮 {inp} | 😈 {diff}"
        if not user_text:
            return f"{header}\n\nОпиши ситуацию одним сообщением (где умер/что не получилось)."

        # База “ультра-тиммейт”: короткий, конкретный разбор
        return (
            f"{header}\n\n"
            f"Получил: {user_text}\n\n"
            "План (1 минута):\n"
            "1) Назови место/тайминг (куда смотрел, откуда прилетело).\n"
            "2) Один главный косяк: позиция / мувмент / аим.\n"
            "3) Следующий повтор: что делаешь иначе (1 действие).\n\n"
            "Кинь: карта/режим/оружие и что именно болит (аим/мувмент/позиционка) — докручу."
        )
