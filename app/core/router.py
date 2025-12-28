from app.ui.quickbar import kb_main, kb_games, kb_roles
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

        # ---------- GAME ----------
        if text == "🎮 Игра":
            await self.tg.send_message(chat_id, "Выбери игру:", reply_markup=kb_games())
            return

        if text == "🔥 Warzone":
            p.game = "warzone"
            await self.tg.send_message(chat_id, "Warzone — выбери роль:", reply_markup=kb_roles("warzone"))
            return

        if text == "🪖 BF6":
            p.game = "bf6"
            await self.tg.send_message(chat_id, "BF6 — select class:", reply_markup=kb_roles("bf6"))
            return

        if text == "💣 BO7":
            p.game = "bo7"
            await self.tg.send_message(chat_id, "BO7 — выбери роль:", reply_markup=kb_roles("bo7"))
            return

        # ---------- ROLES ----------
        if text in (
            "🎯 AR", "💥 SMG", "🔭 Sniper", "🛡 Support",
            "ASSAULT", "ENGINEER", "SUPPORT", "RECON",
            "⚔️ Slayer", "🧠 Tactical", "🛡 Anchor", "💣 Objective",
        ):
            reply = await self.brain.handle_text(user_id, f"CLASS_{text}")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # ---------- DEFAULT ----------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
