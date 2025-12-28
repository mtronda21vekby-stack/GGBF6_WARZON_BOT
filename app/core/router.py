from app.ui.quickbar import kb_main, kb_training, kb_zombies
from app.ui import texts
from zombies.coach import parse_player_input, zombie_coach_reply


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

        # -------- SMART ZOMBIE COACH --------
        parsed = parse_player_input(text)
        if parsed.get("round") or parsed.get("death"):
            reply = zombie_coach_reply(parsed)
            await self.tg.send_message(chat_id, reply, reply_markup=kb_main())
            return

        # -------- START --------
        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # -------- ZOMBIES MENU --------
        if text == "🧟 Zombies":
            await self.tg.send_message(chat_id, "Выбери режим Zombies:", reply_markup=kb_zombies())
            return

        if text == "🧟 Новичок":
            r = await self.brain.handle_text(user_id, "ZOMBIE_BEGINNER")
            await self.tg.send_message(chat_id, r.text, reply_markup=kb_main())
            return

        if text == "🔥 Про":
            r = await self.brain.handle_text(user_id, "ZOMBIE_PRO")
            await self.tg.send_message(chat_id, r.text, reply_markup=kb_main())
            return

        if text == "😈 Demon":
            r = await self.brain.handle_text(user_id, "ZOMBIE_DEMON")
            await self.tg.send_message(chat_id, r.text, reply_markup=kb_main())
            return

        # -------- TRAINING --------
        if text == "🎯 Тренировка":
            await self.tg.send_message(chat_id, "Выбери длительность:", reply_markup=kb_training())
            return

        if text in ("⏱ 15 мин", "⏱ 30 мин", "⏱ 60 мин"):
            key = text.replace("⏱ ", "").replace(" мин", "")
            r = await self.brain.handle_text(user_id, f"TRAIN_{key}")
            await self.tg.send_message(chat_id, r.text, reply_markup=kb_main())
            return

        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # -------- DEFAULT --------
        r = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, r.text, reply_markup=kb_main())
