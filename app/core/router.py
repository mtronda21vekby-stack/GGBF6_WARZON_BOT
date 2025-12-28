from app.ui.quickbar import kb_main, kb_ai, kb_premium, kb_profile, kb_roles
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
            await self.tg.send_message(chat_id, "Выбери стиль анализа:", reply_markup=kb_ai())
            return

        if text == "😈 Demon-анализ":
            profile.mode = "demon"
            await self.tg.send_message(chat_id, "😈 Demon активен. Пиши ситуацию.", reply_markup=kb_main())
            return

        if text == "🔥 Pro-анализ":
            profile.mode = "pro"
            await self.tg.send_message(chat_id, "🔥 Pro активен. Пиши ситуацию.", reply_markup=kb_main())
            return

        if text == "🧠 Общий разбор":
            profile.mode = "normal"
            await self.tg.send_message(chat_id, "🧠 Normal активен. Пиши ситуацию.", reply_markup=kb_main())
            return

        # ---------- PREMIUM ----------
        if text == "💎 Premium":
            await self.tg.send_message(chat_id, "Premium-меню:", reply_markup=kb_premium())
            return

        if text == "💎 Что даёт Premium":
            await self.tg.send_message(
                chat_id,
                "💎 PREMIUM:\n• инсайты топ-1%\n• жёсткий Demon\n• глубокая память\n• будущий реальный ИИ\n\nПока OFF.",
                reply_markup=kb_main(),
            )
            return

        # ---------- ROLE ----------
        if text == "🎭 Роль":
            g = (profile.game or "warzone").lower()
            await self.tg.send_message(chat_id, "Выбери роль:", reply_markup=kb_roles(g))
            return

        # Warzone roles
        if text in ("🎭 Entry", "🎭 Anchor", "🎭 Sniper"):
            role = text.replace("🎭 ", "").lower()
            profile.role = role
            await self.tg.send_message(chat_id, f"✅ Роль выбрана: {role.upper()}", reply_markup=kb_main())
            return

        # BF6 roles
        if text in ("🎭 Assault", "🎭 Engineer", "🎭 Support", "🎭 Recon"):
            role = text.replace("🎭 ", "").lower()
            profile.role = role
            await self.tg.send_message(chat_id, f"✅ Class set: {role.upper()}", reply_markup=kb_main())
            return

        # BO7 roles
        if text in ("🎭 Slayer", "🎭 Objective"):
            role = text.replace("🎭 ", "").lower()
            profile.role = role
            await self.tg.send_message(chat_id, f"✅ Роль выбрана: {role.upper()}", reply_markup=kb_main())
            return

        # ---------- PROFILE ----------
        if text == "📌 Профиль":
            await self.tg.send_message(chat_id, "Профиль:", reply_markup=kb_profile())
            return

        if text == "📈 Статистика":
            lvl = self.brain.rating.level(user_id)
            score = self.brain.rating.get(user_id)
            g = (profile.game or "warzone").upper()
            m = (profile.mode or "normal").upper()
            r = (getattr(profile, "role", None) or "—").upper()
            s = self.brain.season.season_id
            await self.tg.send_message(
                chat_id,
                f"📈 СТАТИСТИКА\n\n🎮 {g}\n😈 {m}\n🎭 {r}\n📊 Рейтинг: {lvl} ({score})\n🗓 Сезон: {s}",
                reply_markup=kb_main(),
            )
            return

        if text == "🗓 Сезон":
            s = self.brain.season.season_id
            await self.tg.send_message(chat_id, f"🗓 Текущий сезон: {s}", reply_markup=kb_main())
            return

        if text == "♻️ Сброс сезона":
            # сбрасываем рейтинг всем (простая версия) и создаём новый сезон
            self.brain.rating.reset_all()
            self.brain.season.reset_season()
            await self.tg.send_message(
                chat_id,
                f"♻️ Сезон сброшен. Новый сезон: {self.brain.season.season_id}",
                reply_markup=kb_main(),
            )
            return

        # ---------- BACK ----------
        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # ---------- DEFAULT ----------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
