from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class User:
    id: int
    username: str | None = None
    first_name: str | None = None


@dataclass
class Chat:
    id: int


@dataclass
class Message:
    message_id: int
    chat: Chat
    from_user: User
    text: str | None = None


@dataclass
class CallbackQuery:
    id: str
    from_user: User
    data: str | None = None
    message: Message | None = None


@dataclass
class Update:
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None

    @staticmethod
    def parse(raw: dict[str, Any]) -> "Update":
        def parse_user(u: dict[str, Any]) -> User:
            return User(
                id=int(u["id"]),
                username=u.get("username"),
                first_name=u.get("first_name"),
            )

        def parse_chat(c: dict[str, Any]) -> Chat:
            return Chat(id=int(c["id"]))

        def parse_message(m: dict[str, Any]) -> Message:
            return Message(
                message_id=int(m["message_id"]),
                chat=parse_chat(m["chat"]),
                from_user=parse_user(m["from"]),
                text=m.get("text"),
            )

        msg = raw.get("message")
        cq = raw.get("callback_query")

        message_obj = parse_message(msg) if isinstance(msg, dict) else None

        callback_obj = None
        if isinstance(cq, dict):
            callback_obj = CallbackQuery(
                id=str(cq["id"]),
                from_user=parse_user(cq["from"]),
                data=cq.get("data"),
                message=parse_message(cq["message"]) if isinstance(cq.get("message"), dict) else None,
            )

        return Update(
            update_id=int(raw["update_id"]),
            message=message_obj,
            callback_query=callback_obj,
        )
