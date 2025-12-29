# app/adapters/telegram/types.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Update:
    """
    Лёгкий слой над Telegram Update.
    Мы НЕ усложняем, потому что Router работает с dict.
    Главное: не падать на неожиданных полях.
    """

    raw: Dict[str, Any]

    @staticmethod
    def parse(raw: Any) -> Dict[str, Any]:
        # Telegram должен быть dict
        if isinstance(raw, dict):
            return raw
        # если вдруг пришло не то — возвращаем пустое
        return {}
