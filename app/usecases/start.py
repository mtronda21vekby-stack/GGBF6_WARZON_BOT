# app/usecases/start.py
from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


def handle_start() -> Outgoing:
    return Outgoing(
        text="Привет! Я FPS Coach. Опиши ситуацию в игре — разберём и сделаем план.",
        keyboard=KB.main_menu(),
    )
