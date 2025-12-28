from __future__ import annotations
from app.adapters.telegram.types import Update
from app.ui.keyboards import KB


class Router:
    def __init__(self, tg, brain, settings):
        self.tg = tg
        self.brain = brain
        self.settings = settings

    async def handle_update(self, upd: Update):
        # Text messages
        if upd.message and upd.message.text:
            chat_id = upd.message.chat.id
            user_id = upd.message.from_user.id
            text = upd.message.text.strip()

            if text == "/start":
                await self.tg.send_message(
                    chat_id=chat_id,
                    text="Привет! Я FPS Coach. Пиши проблему — дам план тренировки.",
                    reply_markup=KB.main_menu(),
                )
                return

            reply = await self.brain.handle_text(user_id=user_id, text=text)
            await self.tg.send_message(
                chat_id=chat_id,
                text=reply.text,
                reply_markup=KB.main_menu(),
            )
            return

        # Callback кнопки
        if upd.callback_query:
            cq = upd.callback_query
            await self.tg.answer_callback_query(cq.id)

            user_id = cq.from_user.id
            chat_id = cq.message.chat.id if cq.message else None
            data = (cq.data or "").strip()

            if data == "mem_clear":
                self.brain.clear_memory(user_id)
                if chat_id is not None:
                    await self.tg.send_message(chat_id, "🧹 Память очищена.", reply_markup=KB.main_menu())
                return

            if data == "ai_mode":
                enabled = self.brain.toggle_ai(user_id)
                if chat_id is not None:
                    await self.tg.send_message(
                        chat_id,
                        f"🧠 ИИ-режим: {'ON' if enabled else 'OFF'}",
                        reply_markup=KB.main_menu(),
                    )
                return

            if chat_id is not None:
                await self.tg.send_message(chat_id, f"⚙️ {data} (в разработке)", reply_markup=KB.main_menu())
            return
