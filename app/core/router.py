# app/core/router.py
from __future__ import annotations

from app.ui.quickbar import kb_main, kb_settings
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

        # -------- START / MENU --------
        if text in ("/start", "📋 Меню", "Меню"):
            await self.tg.send_message(
                chat_id,
                texts.WELCOME,
                reply_markup=kb_main(),
            )
            return

        # -------- SETTINGS --------
        if text == "⚙️ Настройки":
            await self.tg.send_message(
                chat_id,
                texts.SETTINGS,
                reply_markup=kb_settings(),
            )
            return

        if text.startswith("🎮 Игра:"):
            p.game = text.split(":")[1].strip().lower()
            await self.tg.send_message(chat_id, f"✅ Игра выбрана: {p.game.upper()}", reply_markup=kb_main())
            return

        if "Input:" in text:
            p.device = "pc" if "KBM" in text else "console"
            await self.tg.send_message(chat_id, f"✅ Ввод: {p.device.upper()}", reply_markup=kb_main())
            return

        if "Сложность:" in text:
            if "Normal" in text:
                p.mode = "normal"
            elif "Pro" in text:
                p.mode = "pro"
            elif "Demon" in text:
                p.mode = "demon"
            await self.tg.send_message(chat_id, f"😈 Режим: {p.mode.upper()}", reply_markup=kb_main())
            return

        # -------- PROFILE --------
        if text == "📌 Профиль":
            await self.tg.send_message(
                chat_id,
                f"📌 Профиль:\n🎮 Игра: {p.game}\n🕹 Ввод: {p.device}\n😈 Режим: {p.mode}\n🧠 ИИ: {'ON' if p.ai_enabled else 'OFF'}",
                reply_markup=kb_main(),
            )
            return

        # -------- AI --------
        if text == "🧠 ИИ":
            p.ai_enabled = not p.ai_enabled
            await self.tg.send_message(
                chat_id,
                f"🧠 ИИ: {'ВКЛ' if p.ai_enabled else 'ВЫКЛ'}",
                reply_markup=kb_main(),
            )
            return

        # -------- TRAINING --------
        if text == "🎯 Тренировка":
            await self.tg.send_message(
                chat_id,
                "🎯 Напиши, что хочешь прокачать:\nAIM / MOVEMENT / POSITIONING",
                reply_markup=kb_main(),
            )
            return

        # -------- ZOMBIES --------
        if text == "🧟 Zombies":
            await self.tg.send_message(
                chat_id,
                "🧟 Zombies режим в разработке.\nСкоро будет мясо 😈",
                reply_markup=kb_main(),
            )
            return

        # -------- VOD --------
        if text == "🎬 VOD":
            await self.tg.send_message(
                chat_id,
                "🎬 VOD-анализ:\nОпиши момент или вставь тайминг (скоро загрузка видео).",
                reply_markup=kb_main(),
            )
            return

        # -------- STATUS --------
        if text == "📡 Статус":
            await self.tg.send_message(
                chat_id,
                "📡 Статус: ONLINE\nBrain: ACTIVE\nРежим: {}".format(p.mode.upper()),
                reply_markup=kb_main(),
            )
            return

        # -------- MEMORY --------
        if text == "🧹 Очистить память":
            self.brain.store.clear(user_id)
            await self.tg.send_message(chat_id, "🧹 Память очищена.", reply_markup=kb_main())
            return

        if text == "🧨 Сброс":
            self.profiles.clear(user_id)
            await self.tg.send_message(chat_id, "🧨 Профиль сброшен.", reply_markup=kb_main())
            return

        # -------- DEFAULT → BRAIN --------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
