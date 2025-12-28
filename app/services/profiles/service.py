# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_PROFILE: Dict[str, Any] = {
    "game": "AUTO",
    "platform": "PC",
    "input": "Controller",
    "difficulty": "Normal",
    "role": "Assault",
    "style": "coach",
}


@dataclass
class ProfileService:
    """
    Единый сервис профиля поверх store.
    Router дергает set_game/set_platform/set_input/set_difficulty/set_role
    и всегда получает нормальный dict профиля.
    """
    store: Any

    def get(self, chat_id: int) -> Dict[str, Any]:
        prof = {}

        # совместимость с разными реализациями store
        if self.store and hasattr(self.store, "get_profile"):
            try:
                prof = self.store.get_profile(chat_id) or {}
            except Exception:
                prof = {}
        elif self.store and hasattr(self.store, "get"):
            # если вдруг в другом store профиль лежит иначе — не ломаемся
            prof = {}

        merged = dict(DEFAULT_PROFILE)
        merged.update(prof or {})
        return merged

    # алиасы на всякий
    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        return self.get(chat_id)

    def read(self, chat_id: int) -> Dict[str, Any]:
        return self.get(chat_id)

    def _set(self, chat_id: int, key: str, value: Any) -> None:
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, key, value)
                return
            except Exception:
                pass

        # fallback: если умеем set_profile целиком
        if self.store and hasattr(self.store, "get_profile") and hasattr(self.store, "set_profile"):
            try:
                prof = self.store.get_profile(chat_id) or {}
                prof[key] = value
                self.store.set_profile(chat_id, prof)
                return
            except Exception:
                pass

    def set_game(self, chat_id: int, game: str) -> None:
        self._set(chat_id, "game", game)

    def set_platform(self, chat_id: int, platform: str) -> None:
        self._set(chat_id, "platform", platform)

    def set_input(self, chat_id: int, input_name: str) -> None:
        self._set(chat_id, "input", input_name)

    def set_difficulty(self, chat_id: int, diff: str) -> None:
        self._set(chat_id, "difficulty", diff)

    def set_role(self, chat_id: int, role: str) -> None:
        self._set(chat_id, "role", role)

    def reset(self, chat_id: int) -> None:
        # сброс профиля к дефолту
        if self.store and hasattr(self.store, "reset_profile"):
            try:
                self.store.reset_profile(chat_id)
                return
            except Exception:
                pass

        # fallback: перезапишем
        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, dict(DEFAULT_PROFILE))
            except Exception:
                pass
