# -*- coding: utf-8 -*-
from __future__ import annotations
from app.core.context import Context
from app.services.brain.memory import InMemoryStore
from app.services.profiles.service import ProfileService
from app.ui.keyboards import KB
from app.ui.templates import T

class BrainEngine:
    def __init__(self, store: InMemoryStore, profiles: ProfileService, settings):
        self.store = store
        self.profiles = profiles
        self.settings = settings

    async def handle_message(self, ctx: Context, text: str):
        low = text.lower()

        if low in ("/start", "start"):
            return T.START, KB.main_menu()

        if low in ("/help", "help", "помощь"):
            return T.HELP, KB.main_menu()

        # Твой “premium режим”: любое обычное сообщение будет уходить в “AI ответ”
        # Пока AI можно сделать заглушкой: отвечать “жив”
        # Позже подключим OpenAI — интерфейс уже готов.
        answer = await self._smart_answer(ctx, text)
        self.store.add_turn(ctx.user_id, text, answer)
        return answer, KB.main_menu()

    async def handle_callback(self, ctx: Context, data: str):
        if data == "menu":
            return T.START, KB.main_menu()

        if data == "settings":
            return "⚙️ Настройки", KB.settings()

        if data == "game":
            return "🎮 Выбери игру:", KB.game_pick()

        if data.startswith("set_game:"):
            game = data.split(":", 1)[1]
            self.profiles.set_game(ctx.user_id, game)
            return f"✅ Игра установлена: {game}", KB.main_menu()

        if data == "style":
            return "🎭 Выбери стиль:", KB.style_pick()

        if data.startswith("set_style:"):
            style = data.split(":", 1)[1]
            self.profiles.set_style(ctx.user_id, style)
            return f"✅ Стиль установлен: {style}", KB.main_menu()

        if data == "profile":
            p = self.profiles.get_profile(ctx.user_id)
            return T.PROFILE.format(**p), KB.main_menu()

        if data == "status":
            st = self.store.get(ctx.user_id)
            return T.STATUS.format(game=st.game, style=st.style, mem=len(st.turns)), KB.main_menu()

        if data == "memory_clear":
            self.store.clear_memory(ctx.user_id)
            return T.MEMORY_CLEARED, KB.main_menu()

        if data == "reset":
            self.store.reset(ctx.user_id)
            return T.RESET_OK, KB.main_menu()

        if data in ("daily", "vod", "zombies", "answer", "settings_tz"):
            return T.NOT_IMPLEMENTED, KB.main_menu()

        return "🤷 Не понял кнопку. Открой меню.", KB.main_menu()

    async def _smart_answer(self, ctx: Context, user_text: str) -> str:
        # Тут будет “Brain v3+” с AI.
        # Пока: отвечает “жив” и добавляет стиль/режим.
        st = self.store.get(ctx.user_id)
        if st.style == "short":
            return f"✅ Ок. Режим: {st.game}."
        if st.style == "friendly":
            return f"🙂 Понял! Напиши ситуацию подробнее — помогу. (режим {st.game})"
        if st.style == "coach":
            return f"😈 Дай вводные по ситуации в игре — разберём и сделаем план. (режим {st.game})"
        return f"✅ Принято. (режим {st.game})"
