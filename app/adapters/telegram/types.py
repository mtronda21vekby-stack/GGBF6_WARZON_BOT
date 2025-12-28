# app/adapters/telegram/types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Chat:
    id: int


@dataclass
class User:
    id: int
    username: str | None = None


@dataclass
class Message:
    message_id: int
    chat: Chat
    from_user: User | None
    text: str | None


@dataclass
class Update:
    update_id: int
    message: Message | None

    @staticmethod
    def parse(raw: dict[str, Any]) -> "Update":
        upd_id = int(raw.get("update_id", 0))

        msg_raw = raw.get("message") or raw.get("edited_message")
        if not msg_raw:
            return Update(update_id=upd_id, message=None)

        chat_raw = msg_raw.get("chat") or {}
        from_raw = msg_raw.get("from")

        chat = Chat(id=int(chat_raw.get("id", 0)))

        from_user = None
        if isinstance(from_raw, dict):
            from_user = User(
                id=int(from_raw.get("id", 0)),
                username=from_raw.get("username"),
            )

        msg = Message(
            message_id=int(msg_raw.get("message_id", 0)),
            chat=chat,
            from_user=from_user,
            text=msg_raw.get("text"),
        )
        return Update(update_id=upd_id, message=msg)
