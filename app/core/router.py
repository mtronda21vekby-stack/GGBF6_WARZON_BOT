# -*- coding: utf-8 -*-
from __future__ import annotations
from app.adapters.telegram.client import TelegramClient
from app.adapters.telegram.types import Update
from app.core.context import Context
from app.observability.log import get_logger
from app.ui.keyboards import KB
from app.ui.templates import T

log = get_logger("router")

class Router:
    def __init__(self, tg: TelegramClient, brain, settings):
        self.tg = tg
        self.brain = brain
        self.settings = settings

    async def handle_update(self, upd: Update) -> None:
        # Callback buttons
        if upd.callback_query:
            cq = upd.callback_query
            if cq.message is None:
                return
            chat_id = cq.message.chat.id
            user_id = cq.from_user.id
            ctx = Context(user_id=user_id, chat_id=chat_id, username=cq.from_user.username)
            data = (cq.data or "").strip()

            await self.tg.answer_callback_query(cq.id)
            text, kb = await self.brain.handle_callback(ctx, data)
            if text:
                await self.tg.send_message(chat_id, text, reply_markup=kb)
            return

        # Messages
        if upd.message and upd.message.text is not None:
            msg = upd.message
            chat_id = msg.chat.id
            user_id = (msg.from_user.id if msg.from_user else chat_id)
            ctx = Context(user_id=user_id, chat_id=chat_id, username=(msg.from_user.username if msg.from_user else None))

            text_in = msg.text.strip()

            text, kb = await self.brain.handle_message(ctx, text_in)
            if text:
                await self.tg.send_message(chat_id, text, reply_markup=kb)
