# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InMemoryStore:
    """
    Простая память + профиль в RAM.
    Ничего не урезает: хранит историю диалога и поля профиля.
    """
    memory_max_turns: int = 30

    # chat_id -> list[{"role": "user|assistant", "text": "..."}]
    _messages: Dict[int, List[Dict[str, str]]] = field(default_factory=dict)

    # chat_id -> profile dict
    _profiles: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    def add(self, chat_id: int, role: str, text: str) -> None:
        arr = self._messages.setdefault(chat_id, [])
        arr.append({"role": role, "text": str(text)})

        # обрезаем историю
        max_len = max(1, int(self.memory_max_turns))
        if len(arr) > max_len:
            self._messages[chat_id] = arr[-max_len:]

    def get(self, chat_id: int) -> List[Dict[str, str]]:
        return list(self._messages.get(chat_id, []))

    def clear(self, chat_id: int) -> None:
        self._messages.pop(chat_id, None)
        # профиль НЕ трогаем при “очистить память”
        # (профиль трогает reset через ProfileService)

    def stats(self, chat_id: int) -> dict:
        return {
            "turns": len(self._messages.get(chat_id, [])),
            "memory_max_turns": self.memory_max_turns,
            "has_profile": chat_id in self._profiles,
        }

    # -----------------------
    # PROFILE STORAGE
    # -----------------------
    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        return dict(self._profiles.get(chat_id, {}))

    def set_profile(self, chat_id: int, profile: Dict[str, Any]) -> None:
        self._profiles[chat_id] = dict(profile or {})

    def reset_profile(self, chat_id: int) -> None:
        self._profiles.pop(chat_id, None)

    def set_profile_field(self, chat_id: int, key: str, value: Any) -> None:
        prof = self._profiles.setdefault(chat_id, {})
        prof[key] = value

    def get_profile_field(self, chat_id: int, key: str, default: Any = None) -> Any:
        return self._profiles.get(chat_id, {}).get(key, default)
