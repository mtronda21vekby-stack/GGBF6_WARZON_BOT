# app/adapters/telegram/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Update:
    raw: Dict[str, Any]

    @staticmethod
    def parse(raw: Dict[str, Any]) -> Dict[str, Any]:
        # Router ожидает обычный dict update — так и отдаём.
        return raw or {}
