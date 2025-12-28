from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


def handle_start() -> Outgoing:
    text = (
        "FPS Coach Bot v2 | 🎮 AUTO | 🔁 CHAT | 🤖 AI ON\n\n"
        "Напиши ситуацию/смерть — разберу.\n"
        "Или жми меню 👇"
    )
    return Outgoing(
        text=text,
        inline_keyboard=KB.main_inline(),
        ensure_quickbar=True,
    )
