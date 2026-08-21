# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Mapping

from app.release import (
    API_CONTRACT_VERSION,
    APP_VERSION,
    MINI_APP_RUNTIME,
    RELEASE_CONTRACT,
    TELEGRAM_AUTH_CONTRACT,
    VOICE_RUNTIME,
    runtime_build_metadata,
)
from app.services.analytics.admin_usage import AdminUsageAnalytics

ADMIN_PREFIX = "bco:admin:"
_ADMIN_COMMANDS = {"/admin", "/adminstats", "/admin_stats"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _short(value: Any, fallback: str = "—", limit: int = 40) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bool_state(value: Any, *, yes: str = "ON", no: str = "OFF") -> str:
    return yes if value is True else no


def configured_admin_ids() -> frozenset[int]:
    raw = ",".join(
        part
        for part in (
            str(os.getenv("BCO_ADMIN_TELEGRAM_USER_ID") or "").strip(),
            str(os.getenv("BCO_ADMIN_TELEGRAM_USER_IDS") or "").strip(),
        )
        if part
    )
    out: set[int] = set()
    for token in raw.replace(";", ",").split(","):
        try:
            value = int(token.strip())
        except Exception:
            continue
        if value > 0:
            out.add(value)
    return frozenset(out)


def is_admin_user(user_id: int | None) -> bool:
    return bool(user_id and int(user_id) in configured_admin_ids())


def _buttons(locale: str, active: str) -> dict[str, Any]:
    ru = locale != "en"
    labels = {
        "overview": "◈ ОБЗОР" if ru else "◈ OVERVIEW",
        "users": "👥 USERS",
        "activity": "▤ АКТИВНОСТЬ" if ru else "▤ ACTIVITY",
        "identity": "◎ IDENTITY",
        "intel": "⌁ CROWN INTEL",
        "system": "⚙ SYSTEM",
        "refresh": "↻ ОБНОВИТЬ" if ru else "↻ REFRESH",
        "close": "✕ ЗАКРЫТЬ" if ru else "✕ CLOSE",
    }
    def button(key: str) -> dict[str, str]:
        prefix = "● " if active == key else ""
        return {"text": prefix + labels[key], "callback_data": ADMIN_PREFIX + key}
    return {
        "inline_keyboard": [
            [button("overview"), button("users")],
            [button("activity"), button("identity")],
            [button("intel"), button("system")],
            [button("refresh"), button("close")],
        ]
    }


def render_admin_view(
    dashboard: Mapping[str, Any],
    *,
    view: str = "overview",
    locale: str = "ru",
    system: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    ru = locale != "en"
    d = _mapping(dashboard)
    users = _mapping(d.get("users"))
    activity = _mapping(d.get("activity"))
    identity = _mapping(d.get("identity"))
    premium = _mapping(d.get("premium"))
    intel = _mapping(d.get("intel"))
    sys = _mapping(system)
    header = "BLACK CROWN // ADMIN COMMAND CENTER"
    source = _short(d.get("schema"), "legacy")

    if view == "users":
        text = (
            f"{header}\n\n"
            f"{'ПОЛЬЗОВАТЕЛИ' if ru else 'USERS'}\n"
            f"Unified known — {_int(users.get('unified_known'))}\n"
            f"Telegram tracked — {_int(users.get('tracked_telegram'))}\n"
            f"Canonical accounts — {_int(users.get('canonical_accounts'))}\n\n"
            f"DAU / 24h — {_int(users.get('active_24h'))}\n"
            f"WAU / 7d — {_int(users.get('active_7d'))}\n"
            f"MAU / 30d — {_int(users.get('active_30d'))}\n"
            f"{'Новые 24ч' if ru else 'New 24h'} — {_int(users.get('new_24h'))}\n"
            f"{'Новые 7д' if ru else 'New 7d'} — {_int(users.get('new_7d'))}\n\n"
            f"Premium active — {_int(premium.get('active_accounts'))}\n\n"
            f"{'Без персональных ID. Один canonical account считается один раз.' if ru else 'No personal IDs. One canonical account is counted once.'}"
        )
    elif view == "activity":
        coverage = _int(activity.get("daily_coverage_days"))
        text = (
            f"{header}\n\n"
            f"{'АКТИВНОСТЬ' if ru else 'ACTIVITY'}\n"
            f"Today updates — {_int(activity.get('today_updates'))}\n"
            f"Today messages — {_int(activity.get('today_messages'))}\n"
            f"Today voice — {_int(activity.get('today_voice'))}\n"
            f"Today Mini App — {_int(activity.get('today_miniapp'))}\n\n"
            f"7d updates — {_int(activity.get('week_updates'))}\n"
            f"7d messages — {_int(activity.get('week_messages'))}\n"
            f"7d voice — {_int(activity.get('week_voice'))}\n"
            f"7d Mini App — {_int(activity.get('week_miniapp'))}\n\n"
            f"Lifetime updates — {_int(activity.get('total_updates'))}\n"
            f"Lifetime messages — {_int(activity.get('total_messages'))}\n"
            f"Lifetime voice — {_int(activity.get('total_voice'))}\n"
            f"Lifetime Mini App — {_int(activity.get('total_miniapp'))}\n\n"
            f"Daily ledger coverage — {coverage} {'дн.' if ru else 'days'}"
        )
    elif view == "identity":
        text = (
            f"{header}\n\n"
            "CROWN IDENTITY CORE\n"
            f"Accounts — {_int(identity.get('accounts'))}\n"
            f"Active identities — {_int(identity.get('identities'))}\n"
            f"Resolved — {_int(identity.get('resolved'))}\n"
            f"Unresolved — {_int(identity.get('unresolved'))}\n"
            f"Conflict — {_int(identity.get('conflict'))}\n"
            f"Merge pending — {_int(identity.get('merge_pending'))}\n\n"
            f"Canonical dual-write — {_bool_state(identity.get('dual_write'))}\n"
            f"Canonical shadow-read — {_bool_state(identity.get('shadow_read'))}\n"
            f"Client owner authority — OFF\n"
            f"Silent merge — FORBIDDEN"
        )
    elif view == "intel":
        text = (
            f"{header}\n\n"
            "CROWN INTEL\n"
            f"Official snapshots — {_int(intel.get('snapshots'))}\n"
            f"Verified changes — {_int(intel.get('changes'))}\n"
            f"Latest snapshot — {_short(intel.get('latest_snapshot_at'))}\n"
            f"Latest change — {_short(intel.get('latest_change_at'))}\n\n"
            f"{'Источник: только server-side aggregate; содержимое игроков не выводится.' if ru else 'Source: server-side aggregate only; no player content is exposed.'}"
        )
    elif view == "system":
        build = _mapping(sys.get("build"))
        recovery = _mapping(sys.get("recovery"))
        text = (
            f"{header}\n\n"
            "SYSTEM / RELEASE\n"
            f"Product — {APP_VERSION}\n"
            f"Release — {RELEASE_CONTRACT}\n"
            f"Build — {_short(build.get('git_commit_short'))}\n"
            f"Build exact — {_bool_state(build.get('exact'), yes='YES', no='NO')}\n"
            f"API — {API_CONTRACT_VERSION}\n"
            f"Telegram auth — {TELEGRAM_AUTH_CONTRACT}\n"
            f"Mini App — {MINI_APP_RUNTIME}\n"
            f"Voice — {VOICE_RUNTIME}\n\n"
            f"Storage primary — {_bool_state(recovery.get('primary_available'), yes='READY', no='DOWN')}\n"
            f"Probe — {_bool_state(recovery.get('last_probe_ok'), yes='OK', no='FAIL')}\n"
            f"Outbox pending — {_int(recovery.get('outbox_pending'))}\n"
            f"Admin telemetry — {source}"
        )
    else:
        text = (
            f"{header}\n\n"
            f"{'LIVE OVERVIEW' if not ru else 'ОПЕРАТИВНАЯ СВОДКА'}\n"
            f"Unified users — {_int(users.get('unified_known'))}\n"
            f"Active 24h — {_int(users.get('active_24h'))}\n"
            f"Active 7d — {_int(users.get('active_7d'))}\n"
            f"Active 30d — {_int(users.get('active_30d'))}\n"
            f"New 24h — {_int(users.get('new_24h'))}\n\n"
            f"Today messages — {_int(activity.get('today_messages'))}\n"
            f"Today voice — {_int(activity.get('today_voice'))}\n"
            f"Today Mini App — {_int(activity.get('today_miniapp'))}\n\n"
            f"Identity unresolved — {_int(identity.get('unresolved'))}\n"
            f"Identity conflicts — {_int(identity.get('conflict')) + _int(identity.get('merge_pending'))}\n"
            f"CROWN INTEL snapshots — {_int(intel.get('snapshots'))}\n\n"
            f"{'Telegram member count ≠ реальные пользователи BLACK CROWN.' if ru else 'Telegram member count ≠ real BLACK CROWN users.'}"
        )
        view = "overview"
    return text, _buttons(locale, view)


@dataclass
class AdminConsoleController:
    tg: Any
    store: Any
    profiles: Any = None
    settings: Any = None

    def _locale(self, chat_id: int, sender: Mapping[str, Any]) -> str:
        if self.profiles is not None:
            try:
                profile = dict(self.profiles.get(chat_id) or {})
                value = str(profile.get("language_override") or profile.get("language") or "").lower()
                if value.startswith("en"):
                    return "en"
                if value.startswith("ru"):
                    return "ru"
            except Exception:
                pass
        return "en" if str(sender.get("language_code") or "").lower().startswith("en") else "ru"

    async def _dashboard(self) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(AdminUsageAnalytics(self.store).dashboard)
        except Exception:
            return {"schema": "unavailable", "users": {}, "activity": {}, "identity": {}, "premium": {}, "intel": {}}

    async def _system(self) -> dict[str, Any]:
        recovery: dict[str, Any] = {}
        fn = getattr(self.store, "recovery_status", None)
        if callable(fn):
            try:
                raw = await asyncio.to_thread(fn)
                if isinstance(raw, Mapping):
                    recovery = dict(raw)
            except Exception:
                recovery = {}
        return {"build": runtime_build_metadata(), "recovery": recovery}

    async def _show(self, chat_id: int, text: str, markup: dict[str, Any], message_id: int | None = None) -> None:
        if message_id is None:
            await self.tg.send_message(chat_id, text, markup)
            return
        try:
            await self.tg.edit_message(chat_id, message_id, text, markup)
        except Exception:
            await self.tg.send_message(chat_id, text, markup)

    async def _render(self, chat_id: int, sender: Mapping[str, Any], view: str, message_id: int | None = None) -> None:
        dashboard, system = await asyncio.gather(self._dashboard(), self._system())
        text, markup = render_admin_view(dashboard, view=view, locale=self._locale(chat_id, sender), system=system)
        await self._show(chat_id, text, markup, message_id)

    async def maybe_handle(self, raw: Mapping[str, Any]) -> bool:
        message = raw.get("message") or raw.get("edited_message") or {}
        message = message if isinstance(message, Mapping) else {}
        callback = raw.get("callback_query") or {}
        callback = callback if isinstance(callback, Mapping) else {}

        if callback:
            data = str(callback.get("data") or "").strip()
            if not data.startswith(ADMIN_PREFIX):
                return False
            sender = _mapping(callback.get("from"))
            callback_message = _mapping(callback.get("message"))
            chat = _mapping(callback_message.get("chat"))
            try:
                chat_id = int(chat.get("id"))
                user_id = int(sender.get("id"))
                message_id = int(callback_message.get("message_id"))
            except Exception:
                return True
            callback_id = str(callback.get("id") or "")
            if not is_admin_user(user_id) or str(chat.get("type") or "") != "private" or chat_id != user_id:
                if callback_id:
                    try:
                        await self.tg.answer_callback_query(callback_id, "ADMIN access denied.", show_alert=True)
                    except Exception:
                        pass
                return True
            if callback_id:
                try:
                    await self.tg.answer_callback_query(callback_id)
                except Exception:
                    pass
            action = data.removeprefix(ADMIN_PREFIX) or "overview"
            if action == "close":
                try:
                    await self.tg.delete_message(chat_id, message_id)
                except Exception:
                    pass
                return True
            if action == "refresh":
                action = "overview"
            await self._render(chat_id, sender, action, message_id)
            return True

        text = str(message.get("text") or "").strip()
        if text not in _ADMIN_COMMANDS:
            return False
        sender = _mapping(message.get("from"))
        chat = _mapping(message.get("chat"))
        try:
            chat_id = int(chat.get("id"))
            user_id = int(sender.get("id"))
        except Exception:
            return True
        locale = self._locale(chat_id, sender)
        if not is_admin_user(user_id) or str(chat.get("type") or "") != "private" or chat_id != user_id:
            denied = "⛔ Команда доступна только владельцу BLACK CROWN OPS." if locale != "en" else "⛔ This command is restricted to the BLACK CROWN OPS owner."
            await self.tg.send_message(chat_id, denied)
            return True
        await self._render(chat_id, sender, "overview")
        return True
