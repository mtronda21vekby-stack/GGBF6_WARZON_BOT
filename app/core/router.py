# app/core/router.py
from __future__ import annotations

import os

from app.adapters.telegram.client import TelegramClient
from app.adapters.telegram.types import Update
from app.services.brain.engine import BrainEngine
from app.services.profiles.service import ProfileService
from app.ui.quickbar import kb_main, kb_settings
from app.config import Settings


ASSET_KALASH = os.path.join("assets", "kalash_3d.mp4")  # <-- твой файл тут


class Router:
    def __init__(self, tg: TelegramClient, brain: BrainEngine, profiles: ProfileService, settings: Settings):
        self.tg = tg
        self.brain = brain
        self.profiles = profiles
        self.settings = settings

    async def handle_update(self, upd: Update) -> None:
        if not upd.message:
            return

        chat_id = upd.message.chat.id
        user_id = upd.message.from_user.id if upd.message.from_user else chat_id
        text = (upd.message.text or "").strip()

        # /start -> сначала 3D-баннер, потом привет + кнопки
        if text.lower() == "/start":
            # 1) отправляем анимацию (без текста)
            try:
                await self.tg.send_animation_file(chat_id, ASSET_KALASH)
            except Exception:
                # fallback на video
                await self.tg.send_video_file(chat_id, ASSET_KALASH)

            # 2) приветствие
            reply = await self.brain.handle_text(user_id, "/start")
            await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
            return

        # Кнопки
        if text in ("🎮 Игра",):
            p = self.profiles.get(user_id)
            await self.tg.send_message(chat_id, "🎮 Игра — выбери в настройках.", reply_markup=kb_settings(p.get("game", "AUTO")))
            return

        if text in ("⚙️ Настройки",):
            p = self.profiles.get(user_id)
            await self.tg.send_message(chat_id, "⚙️ Настройки — выбери:", reply_markup=kb_settings(p.get("game", "AUTO")))
            return

        if text.startswith("🎮 Игра:"):
            g = text.split(":", 1)[1].strip()
            g_norm = {"Warzone": "WARZONE", "BF6": "BF6", "BO7": "BO7"}.get(g, g.upper())
            self.profiles.update(user_id, game=g_norm)
            await self.tg.send_message(chat_id, f"✅ Игра: {g}", reply_markup=kb_main())
            return

        if ("Input:" in text) or ("Ввод:" in text):
            if "KBM" in text:
                self.profiles.update(user_id, input="KBM")
                await self.tg.send_message(chat_id, "✅ Input: KBM", reply_markup=kb_main())
                return
            if "Controller" in text:
                self.profiles.update(user_id, input="CONTROLLER")
                await self.tg.send_message(chat_id, "✅ Input: Controller", reply_markup=kb_main())
                return

        if "Сложность:" in text:
            if "Normal" in text:
                self.profiles.update(user_id, difficulty="NORMAL")
            elif "Pro" in text:
                self.profiles.update(user_id, difficulty="PRO")
            elif "Demon" in text:
                self.profiles.update(user_id, difficulty="DEMON")
            await self.tg.send_message(chat_id, f"✅ {text}", reply_markup=kb_main())
            return

        if text in ("🧠 ИИ",):
            p = self.profiles.get(user_id)
            new_val = not bool(p.get("ai", True))
            self.profiles.update(user_id, ai=new_val)
            await self.tg.send_message(chat_id, f"🤖 ИИ: {'ON' if new_val else 'OFF'}", reply_markup=kb_main())
            return

        if text in ("📌 Профиль",):
            p = self.profiles.get(user_id)
            await self.tg.send_message(
                chat_id,
                f"📌 Профиль\nИгра: {p.get('game')}\nInput: {p.get('input')}\nСложность: {p.get('difficulty')}\nИИ: {'ON' if p.get('ai') else 'OFF'}",
                reply_markup=kb_main(),
            )
            return

        if text in ("📡 Статус", "/ai_status"):
            await self.tg.send_message(
                chat_id,
                "✅ Я на связи. Напиши: какая игра (Warzone/BF6/BO7), твой input (KBM/Controller) и что болит (аим/мувмент/позиционка).",
                reply_markup=kb_main(),
            )
            return

        if text in ("🧹 Очистить память",):
            self.brain.store.clear(user_id)
            await self.tg.send_message(chat_id, "🧹 Память очищена.", reply_markup=kb_main())
            return

        if text in ("🧨 Сброс",):
            self.brain.store.clear(user_id)
            self.profiles.update(user_id, game="AUTO", input="AUTO", difficulty="NORMAL", ai=True)
            await self.tg.send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=kb_main())
            return

        if text in ("⬅️ Назад",):
            await self.tg.send_message(chat_id, "⬅️ Ок. Главное меню.", reply_markup=kb_main())
            return

        # Обычный текст -> brain
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
