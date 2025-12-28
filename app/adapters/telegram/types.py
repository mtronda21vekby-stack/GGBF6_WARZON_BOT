# app/adapters/telegram/types.py  (НОВЫЙ ФАЙЛ)
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Chat:
    id: int


@dataclass
class User:
    id: int


@dataclass
class Message:
    chat: Chat
    from_user: User
    text: str | None = None


@dataclass
class Update:
    message: Message | None = None

    @staticmethod
    def parse(raw: dict) -> "Update":
        msg = raw.get("message")
        if not msg:
            return Update(message=None)

        chat_id = msg.get("chat", {}).get("id")
        user_id = msg.get("from", {}).get("id")
        text = msg.get("text")

        if chat_id is None or user_id is None:
            return Update(message=None)

        return Update(
            message=Message(
                chat=Chat(id=int(chat_id)),
                from_user=User(id=int(user_id)),
                text=text,
            )
        )
