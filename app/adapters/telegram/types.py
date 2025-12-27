# -*- coding: utf-8 -*-
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class User(BaseModel):
    id: int
    is_bot: Optional[bool] = None
    first_name: Optional[str] = None
    username: Optional[str] = None

class Chat(BaseModel):
    id: int
    type: Optional[str] = None

class Message(BaseModel):
    message_id: int
    date: Optional[int] = None
    chat: Chat
    from_user: Optional[User] = None
    text: Optional[str] = None

class CallbackQuery(BaseModel):
    id: str
    from_user: User
    data: Optional[str] = None
    message: Optional[Message] = None

class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None

    @staticmethod
    def parse(raw: Dict[str, Any]) -> "Update":
        # Telegram fields "from" conflict with python keyword
        def fix_message(msg: Dict[str, Any]) -> Dict[str, Any]:
            if "from" in msg and "from_user" not in msg:
                msg["from_user"] = msg.pop("from")
            return msg

        if "message" in raw and isinstance(raw["message"], dict):
            raw["message"] = fix_message(raw["message"])
        if "callback_query" in raw and isinstance(raw["callback_query"], dict):
            cq = raw["callback_query"]
            if "from" in cq and "from_user" not in cq:
                cq["from_user"] = cq.pop("from")
            if "message" in cq and isinstance(cq["message"], dict):
                cq["message"] = fix_message(cq["message"])
        return Update.model_validate(raw)
