# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.entitlements.service import EntitlementStatus, PremiumEntitlementService
from app.ui.quickbar import kb_premium, kb_premium_unlink_confirm

log = logging.getLogger("bco.entitlements.telegram")

_OPEN_COMMANDS = {"💎 Premium", "/premium"}
_LINK_COMMANDS = {"🔗 Связать с сайтом", "/link"}
_STATUS_COMMANDS = {"💳 Premium статус", "/premium_status"}
_UNLINK_COMMANDS = {"🔓 Отвязать сайт", "/unlink"}
_CONFIRM_UNLINK = {"⚠️ Подтвердить отвязку"}
_CANCEL_UNLINK = {"Отмена", "⬅️ Назад"}


def _extract(raw: dict) -> tuple[int | None, int | None, str | None, str, str]:
    message = raw.get("message") or raw.get("edited_message") or {}
    if not isinstance(message, dict):
        return None, None, None, "", ""
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    try:
        chat_id = int(chat.get("id"))
    except Exception:
        chat_id = None
    try:
        user_id = int(sender.get("id"))
    except Exception:
        user_id = None
    username = str(sender.get("username") or "").strip() or None
    chat_type = str(chat.get("type") or "").strip().lower()
    text = str(message.get("text") or "").strip()
    return chat_id, user_id, username, chat_type, text


def _status_lines(status: EntitlementStatus) -> list[str]:
    if not status.linked:
        return [
            "Связка с сайтом: НЕ АКТИВНА",
            "Premium: НЕ АКТИВЕН",
        ]
    if status.premium:
        return [
            "Связка с сайтом: АКТИВНА",
            "Premium: ACTIVE ✅",
            "Источник: server entitlement `bco_premium`",
        ]
    return [
        "Связка с сайтом: АКТИВНА",
        "Premium: пока НЕ АКТИВЕН",
        "Привязка аккаунта сама по себе не является оплатой.",
    ]


@dataclass
class EntitlementTelegramController:
    tg: Any
    service: PremiumEntitlementService
    pending_unlink: dict[int, float] = field(default_factory=dict)

    async def _send_hub(self, chat_id: int, user_id: int, prefix: str = "") -> None:
        try:
            status = await self.service.get_status(user_id)
            lines = _status_lines(status)
        except Exception as exc:
            log.warning("Premium status unavailable user_id=%s error=%s", user_id, type(exc).__name__)
            lines = [
                "Связка/Premium: STATUS OFFLINE",
                "Бот продолжает работать. Серверный статус можно повторить позже.",
            ]

        body = (
            (prefix + "\n\n" if prefix else "")
            + "💎 BLACK CROWN PREMIUM\n\n"
            + "\n".join(lines)
            + "\n\n"
            + "Связать аккаунты: нажми «🔗 Связать с сайтом».\n"
            + "Premium учитывается только из общего Supabase GAME."
        )
        await self.tg.send_message(chat_id, body, kb_premium())

    async def _private_required(self, chat_id: int) -> None:
        await self.tg.send_message(
            chat_id,
            "🔐 Привязка доступна только в личном чате с ботом.\n"
            "Открой @GGBF6_WARZON_BOT напрямую и повтори команду.",
            kb_premium(),
        )

    async def _create_link(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        chat_type: str,
    ) -> None:
        if chat_type != "private":
            await self._private_required(chat_id)
            return
        if not self.service.configured:
            await self.tg.send_message(
                chat_id,
                "⚠️ ACCOUNT BRIDGE сейчас не настроен. Текущие функции бота продолжают работать.",
                kb_premium(),
            )
            return

        try:
            challenge = await self.service.create_link_challenge(
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
            )
        except Exception as exc:
            log.warning("Premium link challenge failed user_id=%s error=%s", user_id, type(exc).__name__)
            await self.tg.send_message(
                chat_id,
                "⚠️ Не удалось создать одноразовую ссылку. Повтори через несколько секунд.",
                kb_premium(),
            )
            return

        minutes = max(1, challenge.ttl_seconds // 60)
        inline = {
            "inline_keyboard": [
                [{"text": "🔗 Связать с BlackCrown", "url": challenge.url}],
            ]
        }
        await self.tg.send_message(
            chat_id,
            "🔗 ОДНОРАЗОВАЯ ПРИВЯЗКА\n\n"
            f"Ссылка действует примерно {minutes} мин.\n"
            "Открой её, проверь текущий аккаунт сайта и нажми «Связать аккаунты».\n\n"
            "Важно:\n"
            "• код хранится в базе только как SHA-256\n"
            "• повторное использование невозможно\n"
            "• привязка НЕ выдаёт Premium и НЕ создаёт покупку",
            inline,
        )

    async def _request_unlink(self, chat_id: int, user_id: int, chat_type: str) -> None:
        if chat_type != "private":
            await self._private_required(chat_id)
            return
        self.pending_unlink[user_id] = time.monotonic() + 60.0
        # Bound stale entries without a background task.
        if len(self.pending_unlink) > 500:
            now = time.monotonic()
            self.pending_unlink = {uid: expiry for uid, expiry in self.pending_unlink.items() if expiry > now}
        await self.tg.send_message(
            chat_id,
            "⚠️ Подтверди отвязку в течение 60 секунд.\n\n"
            "Entitlements и покупки не удаляются. Удаляется только связь сайта с этим Telegram.",
            kb_premium_unlink_confirm(),
        )

    async def _confirm_unlink(self, chat_id: int, user_id: int, chat_type: str) -> None:
        if chat_type != "private":
            await self._private_required(chat_id)
            return
        expires = self.pending_unlink.pop(user_id, 0.0)
        if expires <= time.monotonic():
            await self._send_hub(chat_id, user_id, "⏳ Подтверждение истекло. Начни отвязку заново.")
            return
        try:
            removed = await self.service.unlink(user_id)
        except Exception as exc:
            log.warning("Premium unlink failed user_id=%s error=%s", user_id, type(exc).__name__)
            await self._send_hub(chat_id, user_id, "⚠️ Отвязка временно недоступна.")
            return
        message = "✅ Аккаунты отвязаны." if removed else "ℹ️ Активной связки не было."
        await self._send_hub(chat_id, user_id, message)

    async def maybe_handle_command(self, raw: dict) -> bool:
        chat_id, user_id, username, chat_type, text = _extract(raw)
        if chat_id is None or user_id is None or not text:
            return False

        if text in _OPEN_COMMANDS or text in _STATUS_COMMANDS:
            await self._send_hub(chat_id, user_id)
            return True
        if text in _LINK_COMMANDS:
            await self._create_link(chat_id, user_id, username, chat_type)
            return True
        if text in _UNLINK_COMMANDS:
            await self._request_unlink(chat_id, user_id, chat_type)
            return True
        if text in _CONFIRM_UNLINK:
            await self._confirm_unlink(chat_id, user_id, chat_type)
            return True
        if text in _CANCEL_UNLINK and user_id in self.pending_unlink:
            self.pending_unlink.pop(user_id, None)
            await self._send_hub(chat_id, user_id, "Отвязка отменена.")
            return True
        return False
