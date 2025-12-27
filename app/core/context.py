# -*- coding: utf-8 -*-
from dataclasses import dataclass

@dataclass
class Context:
    user_id: int
    chat_id: int
    username: str | None = None
