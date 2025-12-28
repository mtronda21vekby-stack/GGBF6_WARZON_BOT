from app.ui.quickbar import kb_main, kb_training, kb_zombies
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

        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # ---------- ZOMBIES ----------
        if text == "🧟 Zombies":
            await self.tg.send_message(
                chat_id,
                "Выбери уровень Zombies:",
                reply_markup=kb_zombies(),
            )
            return

        if text == "🧟 Новичок":
            reply = await self.brain.handle_text(user_id, "ZOMBIE_BEGINNER")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "🔥 Про":
            reply = await self.brain.handle_text(user_id, "ZOMBIE_PRO")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "😈 Demon":
            reply = await self.brain.handle_text(user_id, "ZOMBIE_DEMON")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        # ---------- TRAINING ----------
        if text == "🎯 Тренировка":
            await self.tg.send_message(
                chat_id,
                "Выбери длительность тренировки:",
                reply_markup=kb_training(),
            )
            return

        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # ---------- DEFAULT ----------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
