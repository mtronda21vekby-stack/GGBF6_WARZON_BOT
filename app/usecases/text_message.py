# app/usecases/text_message.py
from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


async def handle_text_message(brain, user_id: int, text: str) -> Outgoing:
    reply = await brain.handle_text(user_id=user_id, text=text)
    return Outgoing(text=reply.text, keyboard=KB.main_menu())
