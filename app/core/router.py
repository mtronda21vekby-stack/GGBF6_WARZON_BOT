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

    async def _ensure_quickbar(self, chat_id: int, user_id: int):
        p = self.profiles.get(user_id)
        if not p.quickbar_sent:
            await self.tg.send_message(
                chat_id=chat_id,
                text="⬇️ Быстрые кнопки снизу активны.",
                reply_markup=quickbar(),
            )
            p.quickbar_sent = True

    async def _send(self, chat_id: int, user_id: int, out):
        if out.ensure_quickbar:
            await self._ensure_quickbar(chat_id, user_id)

        # основное сообщение (обычно с inline клавой)
        await self.tg.send_message(
            chat_id=chat_id,
            text=out.text,
            reply_markup=out.inline_keyboard,
        )

    async def handle_update(self, upd: Update):
        # TEXT
        if upd.message and upd.message.text:
            chat_id = upd.message.chat.id
            user_id = upd.message.from_user.id
            text = (upd.message.text or "").strip()

            if text == "/start":
                out = handle_start()
                await self._send(chat_id, user_id, out)
                return

            out = await handle_text_message(
                self.brain,
                self.profiles,
                handle_callback,
                user_id,
                text,
            )
            await self._send(chat_id, user_id, out)
            return

        # CALLBACK
        if upd.callback_query:
            cq = upd.callback_query
            await self.tg.answer_callback_query(cq.id)

            user_id = cq.from_user.id
            chat_id = cq.message.chat.id if cq.message else None
            data = cq.data or ""

            out = await handle_callback(self.brain, self.profiles, user_id, data)
            if chat_id is not None:
                await self._send(chat_id, user_id, out)
            return
