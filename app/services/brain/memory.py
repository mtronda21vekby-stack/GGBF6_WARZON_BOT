# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InMemoryStore:
    """
    Лёгкая память в RAM.
    Ничего не режем: add/get/clear/stats.
    Главное: принимает И positional, И keyword аргументы.
    """
    memory_max_turns: int = 24
    _chat: Dict[int, List[Tuple[str, str]]] = field(default_factory=dict)
    _meta: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def __init__(self, memory_max_turns: int = 24, **kwargs):
        # ✅ поддерживаем любые старые варианты имен
        if "max_turns" in kwargs and isinstance(kwargs["max_turns"], int):
            memory_max_turns = kwargs["max_turns"]
        if "memory_max_turns" in kwargs and isinstance(kwargs["memory_max_turns"], int):
            memory_max_turns = kwargs["memory_max_turns"]

        object.__setattr__(self, "memory_max_turns", int(memory_max_turns or 24))
        object.__setattr__(self, "_chat", {})
        object.__setattr__(self, "_meta", {})

    def add(self, chat_id: int, role: str, text: str) -> None:
        role = (role or "user").strip()
        text = (text or "").strip()
        if not text:
            return
        buf = self._chat.setdefault(chat_id, [])
        buf.append((role, text))

        # держим окно памяти
        limit = max(2, int(self.memory_max_turns) * 2)  # user+assistant
        if len(buf) > limit:
            self._chat[chat_id] = buf[-limit:]

    def get(self, chat_id: int) -> List[Dict[str, str]]:
        buf = self._chat.get(chat_id, [])
        return [{"role": r, "text": t} for (r, t) in buf]

    def clear(self, chat_id: int) -> None:
        self._chat.pop(chat_id, None)
        self._meta.pop(chat_id, None)

    def stats(self, chat_id: int) -> Dict[str, Any]:
        buf = self._chat.get(chat_id, [])
        return {
            "turns": len(buf),
            "memory_max_turns": self.memory_max_turns,
        }
