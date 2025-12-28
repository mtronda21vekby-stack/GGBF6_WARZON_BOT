from __future__ import annotations

from app.ui.quickbar import kb_main, kb_settings, kb_game, kb_mode, kb_ai
from app.ui import texts


class Router:
    def __init__(self, tg, brain, settings, profiles):
        self.tg = tg
        self.brain = brain
        self.settings = settings
        self.profiles = profiles

    async def handle_update(self, upd):
        if not upd.message or not (upd.message.text or "").strip():
            return

        chat_id = upd.message.chat.id
        user_id = upd.message.from_user.id
        text = (upd.message.text or "").strip()

        p = self.profiles.get(user_id)

        # START / MENU
        if text in ("/start", "📋 Меню", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # NAV
        if text == "⚙️ Настройки":
            await self.tg.send_message(chat_id, texts.SETTINGS, reply_markup=kb_settings())
            return

        if text == "🎮 Игра":
            await self.tg.send_message(chat_id, texts.GAME_PANEL, reply_markup=kb_game())
            return

        if text == "🎭 Режим":
            await self.tg.send_message(chat_id, texts.MODE_PANEL, reply_markup=kb_mode())
            return

        if text == "🧠 ИИ":
            await self.tg.send_message(chat_id, texts.AI_PANEL, reply_markup=kb_ai())
            return

        if text == "🆘 Помощь":
            await self.tg.send_message(chat_id, texts.HELP, reply_markup=kb_main())
            return

        if text == "🧟 Zombies":
            await self.tg.send_message(chat_id, texts.ZOMBIES_SOON, reply_markup=kb_main())
            return

        if text == "🎬 VOD":
            await self.tg.send_message(chat_id, texts.VOD_SOON, reply_markup=kb_main())
            return

        # SETTINGS: game
        if text in ("🎮 Warzone", "🎮 BF6", "🎮 BO7"):
            p.game = {"🎮 Warzone": "warzone", "🎮 BF6": "bf6", "🎮 BO7": "bo7"}[text]
            await self.tg.send_message(chat_id, f"✅ Игра: {p.game.upper()}", reply_markup=kb_settings())
            return

        # SETTINGS: device
        if text in ("💻 ПК (KBM)", "🎮 PlayStation", "🎮 Xbox"):
            p.device = {"💻 ПК (KBM)": "pc", "🎮 PlayStation": "ps", "🎮 Xbox": "xbox"}[text]
            await self.tg.send_message(chat_id, f"✅ Устройство: {p.device.upper()}", reply_markup=kb_settings())
            return

        # SETTINGS: mode
        if text in ("🙂 Обычный", "🔥 Профи", "😈 Демон"):
            p.mode = {"🙂 Обычный": "normal", "🔥 Профи": "pro", "😈 Демон": "demon"}[text]
            await self.tg.send_message(chat_id, f"✅ Режим: {p.mode.upper()}", reply_markup=kb_settings())
            return

        # AI toggles
        if text == "🧠 ИИ: ВКЛ":
            p.ai_enabled = True
            await self.tg.send_message(chat_id, "✅ ИИ включён", reply_markup=kb_main())
            return

        if text == "🧠 ИИ: ВЫКЛ":
            p.ai_enabled = False
            await self.tg.send_message(chat_id, "✅ ИИ выключен (пока будет коуч-режим без API)", reply_markup=kb_main())
            return

        # status/profile
        if text in ("📡 Статус", "👤 Профиль"):
            await self.tg.send_message(
                chat_id,
                f"📌 Профиль:\n🎮 {p.game.upper()}\n🕹 {p.device.upper()}\n🎭 {p.mode.upper()}\n🧠 ИИ: {'ON' if p.ai_enabled else 'OFF'}\n🧠 Память: {'ON' if p.memory_enabled else 'OFF'}",
                reply_markup=kb_main(),
            )
            return

        # memory
        if text == "🧠 Очистить память":
            self.brain.store.clear(user_id)
            await self.tg.send_message(chat_id, "🧠 Память очищена ✅", reply_markup=kb_main())
            return

        # reset
        if text == "🧨 Сброс":
            self.profiles.clear(user_id)
            await self.tg.send_message(chat_id, "🧨 Сброс выполнен ✅", reply_markup=kb_main())
            return

        # TRAIN placeholder
        if text == "🎯 Тренировка":
            await self.tg.send_message(chat_id, "🎯 Напиши: что не получается (aim/movement/позиционка) и сколько времени есть (15/30/60).", reply_markup=kb_main())
            return

        # MAIN BRAIN
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
