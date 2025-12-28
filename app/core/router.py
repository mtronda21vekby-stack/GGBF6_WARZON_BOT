from app.ui.quickbar import kb_main
from app.ui.roles import kb_roles, role_from_text
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

        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # -------- ROLE --------
        if text == "🎭 Роль":
            await self.tg.send_message(
                chat_id,
                "🎭 Выбери роль — это меняет мышление бота:",
                reply_markup=kb_roles(),
            )
            return

        role = role_from_text(text)
        if role:
            profile.role = role
            await self.tg.send_message(
                chat_id,
                f"✅ Роль установлена: {role.upper()}",
                reply_markup=kb_main(),
            )
            return

        # -------- DEFAULT --------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
