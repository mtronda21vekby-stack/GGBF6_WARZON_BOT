# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class AdminUsageAnalytics:
    store: Any

    def _primary(self) -> Any:
        return getattr(self.store, "primary", self.store)

    def _rpc_rows(self, name: str, payload: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        primary = self._primary()
        request = getattr(primary, "_request", None)
        rows_fn = getattr(primary, "_rows", None)
        if not callable(request) or not callable(rows_fn):
            return []
        rows = rows_fn(request("POST", f"rpc/{name}", json=dict(payload or {})))
        return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]

    def record(
        self,
        *,
        user_id: int,
        chat_id: int,
        language: str,
        surface: str,
        is_message: bool = False,
        is_voice: bool = False,
        is_miniapp: bool = False,
    ) -> None:
        primary = self._primary()
        request = getattr(primary, "_request", None)
        if callable(request):
            request(
                "POST",
                "rpc/bco_record_user_activity",
                json={
                    "p_user_id": int(user_id),
                    "p_chat_id": int(chat_id),
                    "p_language": str(language or "")[:16],
                    "p_surface": str(surface or "telegram")[:32],
                    "p_is_message": bool(is_message),
                    "p_is_voice": bool(is_voice),
                    "p_is_miniapp": bool(is_miniapp),
                },
                extra_headers={"Prefer": "return=minimal"},
            )

    def summary(self) -> dict[str, int]:
        rows = self._rpc_rows("bco_admin_usage_summary")
        raw = dict(rows[0]) if rows else {}
        return {str(k): int(v or 0) for k, v in raw.items()}

    def dashboard(self) -> dict[str, Any]:
        """Return aggregate-only admin intelligence.

        The v1 RPC is intentionally service-role only and returns no Telegram IDs,
        canonical IDs, prompts, transcripts, profile fields or other user payload.
        During rollout, missing migration/RPC falls back to the established summary.
        """
        try:
            rows = self._rpc_rows("bco_admin_dashboard_v1")
            if rows:
                payload = rows[0].get("payload")
                if isinstance(payload, Mapping):
                    return dict(payload)
        except Exception:
            pass
        legacy = self.summary()
        return {
            "schema": "bco-admin-dashboard-legacy-fallback",
            "users": {
                "tracked_telegram": legacy.get("total_users", 0),
                "unified_known": legacy.get("total_users", 0),
                "canonical_accounts": 0,
                "active_24h": legacy.get("active_24h", 0),
                "active_7d": legacy.get("active_7d", 0),
                "active_30d": legacy.get("active_30d", 0),
                "new_24h": legacy.get("new_24h", 0),
                "new_7d": legacy.get("new_7d", 0),
            },
            "activity": {
                "total_updates": legacy.get("total_updates", 0),
                "total_messages": legacy.get("total_messages", 0),
                "total_voice": legacy.get("total_voice", 0),
                "total_miniapp": legacy.get("total_miniapp", 0),
                "today_updates": 0,
                "today_messages": 0,
                "today_voice": 0,
                "today_miniapp": 0,
                "today_miniapp_users": 0,
                "week_updates": 0,
                "week_messages": 0,
                "week_voice": 0,
                "week_miniapp": 0,
                "week_miniapp_users": 0,
                "daily_coverage_days": 0,
            },
            "identity": {},
            "premium": {},
            "intel": {},
        }

    @staticmethod
    def render(summary: Mapping[str, Any], locale: str = "ru") -> str:
        """Legacy /adminstats text contract retained for compatibility."""
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
