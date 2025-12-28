from app.ui.quickbar import kb_main, kb_ai, kb_premium
from app.ui import texts


class Router:
    def __init__(self, tg, brain, profiles, settings):
        self.tg = tg
        self.brain = brain
        self.profiles = profiles
        self.settings = settings

    async def handle_update(self, upd):
        if not upd.message or not upd.message.text:
            return

        chat_id = upd.message.chat.id
        user_id = upd.message.from_user.id
        text = upd.message.text.strip()

        profile = self.profiles.get(user_id)

        # ---------- START ----------
        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # ---------- AI ----------
        if text == "🧠 ИИ":
            await self.tg.send_message(
                chat_id,
                "Выбери стиль анализа:",
                reply_markup=kb_ai(),
            )
            return

        if text == "😈 Demon-анализ":
            profile.mode = "demon"
            await self.tg.send_message(
                chat_id,
                "Demon-режим активен. Опиши ситуацию.",
                reply_markup=kb_main(),
            )
            return

        if text == "🔥 Pro-анализ":
            profile.mode = "pro"
            await self.tg.send_message(
                chat_id,
                "Pro-режим активен. Опиши ситуацию.",
                reply_markup=kb_main(),
            )
            return

        if text == "🧠 Общий разбор":
            profile.mode = "normal"
            await self.tg.send_message(
                chat_id,
                "Normal-режим. Опиши ситуацию.",
                reply_markup=kb_main(),
            )
            return

        # ---------- PREMIUM ----------
        if text == "💎 Premium":
            await self.tg.send_message(
                chat_id,
                "Premium-режим (архитектура готова):",
                reply_markup=kb_premium(),
            )
            return

        if text == "💎 Что даёт Premium":
            await self.tg.send_message(
                chat_id,
                (
                    "💎 PREMIUM:\n\n"
                    "• Советы топ-1% игроков\n"
                    "• Более жёсткий Demon-тиммейт\n"
                    "• Глубокая память ошибок\n"
                    "• Будущий реальный ИИ\n\n"
                    "Пока OFF."
                ),
                reply_markup=kb_main(),
            )
            return

        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # ---------- DEFAULT ----------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
