# app/services/brain/memory.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class InMemoryStore:
    """
    Один store = 2 сущности (НЕ ПУТАЕМ):
    1) history: список сообщений user/assistant для AI
    2) profile: настройки пользователя (game/platform/input/difficulty/voice/role/bf6_class)

    Это убирает главную боль:
    - бот "молчит" / "тупит" из-за того, что профиль случайно читается как история или наоборот
    - настройки не сохраняются, voice не влияет и кажется что AI "одинаковый"
    """

    memory_max_turns: int = 20

    # chat_id -> list[{"role": "...", "content": "...", "ts": ...}]
    _history: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)

    # chat_id -> dict profile
    _profiles: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # ---------------- HISTORY API ----------------
    def add(self, chat_id: int, role: str, content: str) -> None:
        if not chat_id:
            return
        r = (role or "").strip().lower()
        if r not in ("user", "assistant", "system"):
            r = "user"
        msg = {"role": r, "content": str(content), "ts": int(time.time())}

        arr = self._history.setdefault(int(chat_id), [])
        arr.append(msg)

        # ограничение по длине: max_turns = пары user+assistant, поэтому держим 2x
        limit = max(2, int(self.memory_max_turns) * 2)
        if len(arr) > limit:
            self._history[int(chat_id)] = arr[-limit:]

    def get(self, chat_id: int) -> List[Dict[str, Any]]:
        return list(self._history.get(int(chat_id), []) or [])

    def clear(self, chat_id: int) -> None:
        self._history.pop(int(chat_id), None)

    def stats(self, chat_id: int) -> Dict[str, Any]:
        h = self._history.get(int(chat_id), []) or []
        p = self._profiles.get(int(chat_id), {}) or {}
        return {
            "turns": len(h),
            "max_turns": int(self.memory_max_turns),
            "profile_keys": sorted(list(p.keys())) if isinstance(p, dict) else [],
        }

    # ---------------- PROFILE API ----------------
    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        v = self._profiles.get(int(chat_id))
        return dict(v) if isinstance(v, dict) else {}

    def set_profile(self, chat_id: int, patch: Dict[str, Any]) -> None:
        if not chat_id:
            return
        cur = self._profiles.get(int(chat_id))
        if not isinstance(cur, dict):
            cur = {}
        if isinstance(patch, dict):
            # patch merge
            for k, v in patch.items():
                if v is None:
                    continue
                cur[str(k)] = v
        self._profiles[int(chat_id)] = cur

    # совместимость с ProfileService (на всякий)
    def read_profile(self, chat_id: int) -> Dict[str, Any]:
        return self.get_profile(chat_id)

    def write_profile(self, chat_id: int, prof: Dict[str, Any]) -> None:
        # перезапись целиком
        if not isinstance(prof, dict):
            return
        self._profiles[int(chat_id)] = dict(prof)

    # иногда удобно
    def reset_profile(self, chat_id: int) -> None:
        self._profiles.pop(int(chat_id), None)
