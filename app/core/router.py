from __future__ import annotations

from app.adapters.telegram.types import Update
from app.ui.quickbar import quickbar
from app.usecases.start import handle_start
from app.usecases.callbacks import handle_callback
from app.usecases.text_message import handle_text_message


class Router:
    def __init__(self, tg, brain, profiles, settings):
        self.tg = tg
        self.brain = brain
        self.profiles = profiles
        self.settings = settings

    async def _send_quickbar(self, chat_id: int):
        # Нижние кнопки (ReplyKeyboard)
        await self.tg.send_message(
            chat_id=chat_id,
            text="⬇️ Быстрые кнопки снизу активны.",
            reply_markup=quickbar(),
        )

    async def _send(self, chat_id: int, text: str, inline_keyboard: dict | None = None):
        await self.tg.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=inline_keyboard,
        )

    async def handle_update(self, upd: Update):
        # ===== TEXT =====
        if upd.message and upd.message.text:
            chat_id = upd.message.chat.id
            user_id = upd.message.from_user.id
            text = (upd.message.text or "").strip()

            # /start
            if text == "/start":
                out = handle_start()

                # 1️⃣ СНАЧАЛА включаем нижние кнопки
                await self._send_quickbar(chat_id)

                # 2️⃣ Потом основное сообщение
                await self._send(
                    chat_id=chat_id,
                    text=out.text,
                    inline_keyboard=out.inline_keyboard,
                )
                return

            # обычный текст
            out = await handle_text_message(
                self.brain,
                self.profiles,
                handle_callback,
                user_id,
                text,
            )

            await self._send(
                chat_id=chat_id,
                text=out.text,
                inline_keyboard=out.inline_keyboard,
            )
            return

        # ===== CALLBACK =====
        if upd.callback_query:
            cq = upd.callback_query
            await self.tg.answer_callback_query(cq.id)

            user_id = cq.from_user.id
            chat_id = cq.message.chat.id if cq.message else None
            data = cq.data or ""

            out = await handle_callback(
                self.brain,
                self.profiles,
                user_id,
                data,
            )

            if chat_id:
                await self._send(
                    chat_id=chat_id,
                    text=out.text,
                    inline_keyboard=out.inline_keyboard,
                )
            return
