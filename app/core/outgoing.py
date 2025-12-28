from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Outgoing:
    text: str
    inline_keyboard: dict | None = None     # inline кнопки на сообщении
    reply_keyboard: dict | None = None      # нижняя “премиум” панель
    ensure_quickbar: bool = False           # просим роутер включить нижние кнопки (один раз)
