# app/adapters/telegram/types.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Update:
    """
    Унифицированный Update, чтобы Router всегда работал одинаково.
    Мы НЕ режем Telegram payload — сохраняем raw полностью,
    но отдаём Router'у обычный dict.
    """
    raw: Dict[str, Any]

    @staticmethod
    def parse(raw: Any) -> Dict[str, Any]:
        """
        Возвращает нормализованный dict.
        Важно: Router ожидает dict с ключами:
        - message / edited_message / callback_query (если будет)
        """
        if raw is None:
            return {}

        # Если вдруг прилетел уже Update
        if isinstance(raw, Update):
            return raw.raw or {}

        # Обычный случай: Telegram прислал dict
        if isinstance(raw, dict):
            return raw

        # Если по какой-то причине прилетело что-то странное — приводим
        try:
            return dict(raw)  # type: ignore
        except Exception:
            return {}
