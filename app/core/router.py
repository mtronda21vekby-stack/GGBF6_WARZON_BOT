from app.ui.quickbar import (
    kb_main, kb_games, kb_platform, kb_input,
    kb_difficulty, kb_settings
)
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

        # -------- START --------
        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # -------- SETTINGS ROOT --------
        if text == "⚙️ Настройки":
            await self.tg.send_message(
                chat_id,
                "⚙️ Настройки профиля\n\nИди сверху вниз — так логичнее.",
                reply_markup=kb_settings(),
            )
            return

        # -------- GAME --------
        if text == "🎮 Выбрать игру":
            await self.tg.send_message(chat_id, "🎮 Выбери игру:", reply_markup=kb_games())
            return

        if text == "🔥 Warzone":
            profile.game = "warzone"
            await self.tg.send_message(chat_id, "✅ Игра: WARZONE", reply_markup=kb_settings())
            return

        if text == "💣 BO7":
            profile.game = "bo7"
            await self.tg.send_message(chat_id, "✅ Игра: BO7", reply_markup=kb_settings())
            return

        if text == "🪖 BF6":
            profile.game = "bf6"
            await self.tg.send_message(chat_id, "✅ Game: BF6", reply_markup=kb_settings())
            return

        # -------- PLATFORM --------
        if text == "🖥 Платформа":
            await self.tg.send_message(chat_id, "🖥 Выбери платформу:", reply_markup=kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            profile.platform = text.replace("🖥 ", "").replace("🎮 ", "").lower()
            await self.tg.send_message(
                chat_id,
                f"✅ Платформа: {profile.platform.upper()}",
                reply_markup=kb_settings(),
            )
            return

        # -------- INPUT --------
        if text == "⌨️ Input":
            await self.tg.send_message(chat_id, "⌨️ Выбери input:", reply_markup=kb_input())
            return

        if text in ("⌨️ KBM", "🎮 Controller"):
            profile.input = "kbm" if "KBM" in text else "controller"
            await self.tg.send_message(
                chat_id,
                f"✅ Input: {profile.input.upper()}",
                reply_markup=kb_settings(),
            )
            return

        # -------- DIFFICULTY --------
        if text == "😈 Режим мышления":
            await self.tg.send_message(chat_id, "😈 Выбери режим:", reply_markup=kb_difficulty())
            return

        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            profile.mode = text.split()[-1].lower()
            await self.tg.send_message(
                chat_id,
                f"✅ Режим: {profile.mode.upper()}",
                reply_markup=kb_settings(),
            )
            return

        # -------- BACK --------
        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # -------- DEFAULT --------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
