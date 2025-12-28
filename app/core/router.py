from app.ui.quickbar import (
    kb_main, kb_ai, kb_premium, kb_profile, kb_roles,
    kb_games, kb_settings, kb_training, kb_zombies
)
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

        profile = self.profiles.get(user_id)

        # -------- SMART ZOMBIE COACH (только ответ, зомби-контент не трогаем) --------
        parsed = parse_player_input(text)
        # если юзер пишет формат "Раунд: ... | Умираю от: ..."
        if parsed.get("round") or parsed.get("death") or parsed.get("map"):
            # если юзер не написал режим — берём из профиля
            if not parsed.get("mode"):
                parsed["mode"] = (profile.mode or "normal")
            reply = zombie_coach_reply(parsed)
            await self.tg.send_message(chat_id, reply, reply_markup=kb_main())
            return

        # -------- START --------
        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # -------- GAME --------
        if text == "🎮 Игра":
            await self.tg.send_message(chat_id, "Выбери игру:", reply_markup=kb_games())
            return

        if text == "🔥 Warzone":
            profile.game = "warzone"
            profile.role = None
            await self.tg.send_message(chat_id, "✅ Игра: WARZONE", reply_markup=kb_main())
            return

        if text == "🪖 BF6":
            profile.game = "bf6"
            profile.role = None
            await self.tg.send_message(chat_id, "✅ Game: BF6", reply_markup=kb_main())
            return

        if text == "💣 BO7":
            profile.game = "bo7"
            profile.role = None
            await self.tg.send_message(chat_id, "✅ Игра: BO7", reply_markup=kb_main())
            return

        # -------- ROLE --------
        if text == "🎭 Роль":
            g = (profile.game or "warzone").lower()
            await self.tg.send_message(chat_id, "Выбери роль:", reply_markup=kb_roles(g))
            return

        if text.startswith("🎭 "):
            role = text.replace("🎭 ", "").strip().lower()
            # нормализуем под loadouts.py
            profile.role = role
            await self.tg.send_message(chat_id, f"✅ Роль выбрана: {role.upper()}", reply_markup=kb_main())
            return

        # -------- SETTINGS --------
        if text == "⚙️ Настройки":
            await self.tg.send_message(chat_id, "⚙️ Настройки профиля:", reply_markup=kb_settings())
            return

        if text.startswith("🎮 Игра:"):
            g = text.split(":", 1)[1].strip().lower()
            if "warzone" in g:
                profile.game = "warzone"
            elif "bf6" in g:
                profile.game = "bf6"
            elif "bo7" in g:
                profile.game = "bo7"
            profile.role = None
            await self.tg.send_message(chat_id, f"✅ Игра выбрана: {profile.game.upper()}", reply_markup=kb_main())
            return

        if "Input:" in text:
            profile.device = "pc" if "KBM" in text else "console"
            await self.tg.send_message(chat_id, f"✅ Input: {profile.device.upper()}", reply_markup=kb_main())
            return

        if "Сложность:" in text:
            if "Normal" in text:
                profile.mode = "normal"
            elif "Pro" in text:
                profile.mode = "pro"
            elif "Demon" in text:
                profile.mode = "demon"
            await self.tg.send_message(chat_id, f"✅ Режим: {profile.mode.upper()}", reply_markup=kb_main())
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

        # -------- AI --------
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

        # -------- VOD --------
        if text == "🎬 VOD":
            await self.tg.send_message(
                chat_id,
                "🎬 VOD:\nНапиши одной строкой:\nКарта | Режим | Как умер | Что хотел сделать\n\nСкоро добавим загрузку видео.",
                reply_markup=kb_main(),
            )
            return

        # -------- ZOMBIES (меню только) --------
        if text == "🧟 Zombies":
            await self.tg.send_message(
                chat_id,
                "🧟 Zombies:\nВыбери карту (контент не трогаем):",
                reply_markup=kb_zombies(),
            )
            return

        if text == "🗺 Ashes":
            profile.zombie_map = "ashes"
            await self.tg.send_message(
                chat_id,
                "✅ Zombies карта: ASHES\n\nПиши:\nРаунд: __ | Умираю от: узко/толпа/спец | Есть: ...",
                reply_markup=kb_main(),
            )
            return

        if text == "🗺 Astra":
            profile.zombie_map = "astra"
            await self.tg.send_message(
                chat_id,
                "✅ Zombies карта: ASTRA\n\nПиши:\nРаунд: __ | Умираю от: узко/толпа/спец | Есть: ...",
                reply_markup=kb_main(),
            )
            return

        # -------- PROFILE --------
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
            await self.tg.send_message(chat_id, f"🗓 Текущий сезон: {self.brain.season.season_id}", reply_markup=kb_main())
            return

        if text == "♻️ Сброс сезона":
            self.brain.rating.reset_all()
            self.brain.season.reset_season()
            await self.tg.send_message(chat_id, f"♻️ Новый сезон: {self.brain.season.season_id}", reply_markup=kb_main())
            return

        # -------- STATUS --------
        if text == "📊 Статус":
            g = (profile.game or "warzone").upper()
            m = (profile.mode or "normal").upper()
            await self.tg.send_message(chat_id, f"📊 ONLINE\n🎮 {g}\n😈 {m}", reply_markup=kb_main())
            return

        # -------- PREMIUM --------
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

        # -------- SERVICE --------
        if text == "🧹 Очистить память":
            try:
                self.brain.store.clear(user_id)
            except Exception:
                pass
            await self.tg.send_message(chat_id, "🧹 Память очищена.", reply_markup=kb_main())
            return

        if text == "🧨 Сброс":
            try:
                self.profiles.clear(user_id)
            except Exception:
                pass
            try:
                self.brain.store.clear(user_id)
            except Exception:
                pass
            await self.tg.send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=kb_main())
            return

        # -------- BACK --------
        if text == "⬅️ Назад":
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # -------- DEFAULT --------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
