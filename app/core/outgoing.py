from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Outgoing:
    text: str
    inline_keyboard: dict | None = None     # inline кнопки на сообщении
    reply_keyboard: dict | None = None      # нижняя панель (ReplyKeyboard)
    ensure_quickbar: bool = False           # попросить включить панель (один раз)
