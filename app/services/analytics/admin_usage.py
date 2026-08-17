# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class AdminUsageAnalytics:
    store: Any

    def _primary(self) -> Any:
        return getattr(self.store, "primary", self.store)

    def record(self, *, user_id: int, chat_id: int, language: str, surface: str, is_message: bool = False, is_voice: bool = False, is_miniapp: bool = False) -> None:
        fn = getattr(self._primary(), "record_user_activity", None)
        if not callable(fn):
            return
        fn(user_id, chat_id, language=language, surface=surface, is_message=is_message, is_voice=is_voice, is_miniapp=is_miniapp)

    def summary(self) -> dict[str, int]:
        fn = getattr(self._primary(), "admin_usage_summary", None)
        if not callable(fn):
            return {}
        raw = fn()
        return {str(k): int(v or 0) for k, v in dict(raw or {}).items()}

    @staticmethod
    def render(summary: Mapping[str, Any], locale: str = "ru") -> str:
        s = {str(k): int(v or 0) for k, v in dict(summary or {}).items()}
        if locale == "en":
            return (
                "BLACK CROWN OPS // ADMIN REPORT\n\n"
                f"TOTAL TRACKED USERS — {s.get('total_users', 0)}\n"
                f"ACTIVE 24H — {s.get('active_24h', 0)}\n"
                f"ACTIVE 7D — {s.get('active_7d', 0)}\n"
                f"ACTIVE 30D — {s.get('active_30d', 0)}\n"
                f"NEW 24H — {s.get('new_24h', 0)}\n"
                f"NEW 7D — {s.get('new_7d', 0)}\n\n"
                f"UPDATES — {s.get('total_updates', 0)}\n"
                f"MESSAGES — {s.get('total_messages', 0)}\n"
                f"VOICE — {s.get('total_voice', 0)}\n"
                f"MINI APP — {s.get('total_miniapp', 0)}\n\n"
                "Authority: server-side Supabase activity ledger. Telegram header member counts are not bot MAU/DAU analytics."
            )
        return (
            "BLACK CROWN OPS // ОТЧЁТ АДМИНА\n\n"
            f"ВСЕ ОТСЛЕЖИВАЕМЫЕ ПОЛЬЗОВАТЕЛИ — {s.get('total_users', 0)}\n"
            f"АКТИВНЫЕ 24Ч — {s.get('active_24h', 0)}\n"
            f"АКТИВНЫЕ 7Д — {s.get('active_7d', 0)}\n"
            f"АКТИВНЫЕ 30Д — {s.get('active_30d', 0)}\n"
            f"НОВЫЕ 24Ч — {s.get('new_24h', 0)}\n"
            f"НОВЫЕ 7Д — {s.get('new_7d', 0)}\n\n"
            f"UPDATES — {s.get('total_updates', 0)}\n"
            f"СООБЩЕНИЯ — {s.get('total_messages', 0)}\n"
            f"VOICE — {s.get('total_voice', 0)}\n"
            f"MINI APP — {s.get('total_miniapp', 0)}\n\n"
            "Источник: серверный activity ledger в Supabase. Число участников в шапке Telegram не является DAU/MAU бота."
        )
