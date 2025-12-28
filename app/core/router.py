from app.ui.quickbar import kb_main, kb_training
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

        p = self.profiles.get(user_id)

        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        if text == "🎯 Тренировка":
            await self.tg.send_message(
                chat_id,
                "Выбери длительность тренировки:",
                reply_markup=kb_training(),
            )
            return

        if text == "⏱ 15 мин":
            reply = await self.brain.handle_text(user_id, "TRAIN_15")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "⏱ 30 мин":
            reply = await self.brain.handle_text(user_id, "TRAIN_30")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "⏱ 60 мин":
            reply = await self.brain.handle_text(user_id, "TRAIN_60")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
