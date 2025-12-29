# app/services/brain/memory.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InMemoryStore:
    """
    Память в RAM (Render free тоже ок).
    Хранит:
    - историю сообщений (для ИИ)
    - профиль пользователя (для настроек/кнопок)
    - простую статистику

    Ничего не режем: поддерживаем любые поля профиля.
    """
    memory_max_turns: int = 20

    _history: Dict[int, List[dict]] = field(default_factory=dict)
    _profiles: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # -------- history --------
    def add(self, chat_id: int, role: str, content: str) -> None:
        if not chat_id:
            return
        role = (role or "").strip()
        if role not in ("user", "assistant", "system"):
            role = "user"

        content = "" if content is None else str(content)

        arr = self._history.setdefault(chat_id, [])
        arr.append({"role": role, "content": content})

        # ограничение памяти
        if self.memory_max_turns and len(arr) > self.memory_max_turns:
            self._history[chat_id] = arr[-self.memory_max_turns :]

    def get(self, chat_id: int) -> List[dict]:
        return list(self._history.get(chat_id, []) or [])

    def clear(self, chat_id: int) -> None:
        self._history.pop(chat_id, None)
        # профиль НЕ трогаем при очистке памяти (это важно)
        # если нужен полный сброс — Router вызывает profiles.reset()

    def stats(self, chat_id: int) -> Dict[str, Any]:
        h = self._history.get(chat_id, []) or []
        p = self._profiles.get(chat_id, {}) or {}
        return {
            "turns": len(h),
            "max_turns": self.memory_max_turns,
            "has_profile": bool(p),
            "profile_keys": list(p.keys())[:20],
        }

    # -------- profile --------
    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        return dict(self._profiles.get(chat_id, {}) or {})

    def set_profile(self, chat_id: int, patch: Dict[str, Any]) -> None:
        if not chat_id:
            return
        cur = self._profiles.get(chat_id, {}) or {}
        if not isinstance(cur, dict):
            cur = {}
        if not isinstance(patch, dict):
            patch = {}

        # обновляем поля, не удаляем существующие
        for k, v in patch.items():
            if v is None:
                continue
            cur[str(k)] = v
        self._profiles[chat_id] = cur

    def wipe_profile(self, chat_id: int) -> None:
        self._profiles.pop(chat_id, None)
