# app/services/profiles/service.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_PROFILE: Dict[str, str] = {
    "game": "Warzone",
    "platform": "PC",
    "input": "Controller",
    "difficulty": "Normal",
    "bf6_class": "Assault",
    "role": "Flex",
    "voice": "TEAMMATE",  # TEAMMATE | COACH
}


@dataclass
class ProfileService:
    """
    Профиль пользователя хранится в store.
    Ничего не режем: поддерживаем любые поля.
    """
    store: Any

    def get(self, chat_id: int) -> Dict[str, str]:
        prof = {}
        if self.store and hasattr(self.store, "get_profile"):
            try:
                prof = self.store.get_profile(chat_id) or {}
            except Exception:
                prof = {}

        # merge defaults
        out = dict(DEFAULT_PROFILE)
        if isinstance(prof, dict):
            for k, v in prof.items():
                if v is not None:
                    out[str(k)] = str(v)
        return out

    # aliases for compatibility
    def get_profile(self, chat_id: int) -> Dict[str, str]:
        return self.get(chat_id)

    def read(self, chat_id: int) -> Dict[str, str]:
        return self.get(chat_id)

    def set(self, chat_id: int, key: str, val: str) -> None:
        self.set_field(chat_id, key, val)

    def set_field(self, chat_id: int, key: str, val: str) -> None:
        if self.store and hasattr(self.store, "set_profile"):
            self.store.set_profile(chat_id, {str(key): str(val)})

    def set_value(self, chat_id: int, key: str, val: str) -> None:
        self.set_field(chat_id, key, val)

    def update(self, chat_id: int, patch: Dict[str, str]) -> None:
        if self.store and hasattr(self.store, "set_profile"):
            self.store.set_profile(chat_id, {str(k): str(v) for k, v in (patch or {}).items()})

    def update_profile(self, chat_id: int, patch: Dict[str, str]) -> None:
        self.update(chat_id, patch)

    def reset(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "set_profile"):
            self.store.set_profile(chat_id, dict(DEFAULT_PROFILE))
