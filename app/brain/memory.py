# app/services/brain/memory.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class MemMsg:
    role: str
    content: str
    ts: float


class InMemoryStore:
    """
    Простая память в RAM (на Render сбрасывается при перезапуске).
    Главное: совместима с разными вызовами конструктора:
      - InMemoryStore(memory_max_turns=20)
      - InMemoryStore(max_turns=20)
      - InMemoryStore(limit=20)
      - InMemoryStore(20)  # позиционно
    """

    def __init__(self, *args, **kwargs):
        # 1) вытащим лимит из kwargs в порядке приоритета
        limit = None
        for k in ("memory_max_turns", "max_turns", "limit", "max_messages", "memory_limit"):
            if k in kwargs and kwargs[k] is not None:
                limit = kwargs[k]
                break

        # 2) если передали позиционно — тоже поддержим
        if limit is None and len(args) >= 1 and args[0] is not None:
            limit = args[0]

        # 3) дефолт
        try:
            self.max_turns = int(limit) if limit is not None else 20
        except Exception:
            self.max_turns = 20

        if self.max_turns < 4:
            self.max_turns = 4  # чтобы не “обнулялось” слишком агрессивно

        self._data: Dict[int, List[MemMsg]] = {}

    # --- core API ---
    def add(self, chat_id: int, role: str, content: str) -> None:
        cid = int(chat_id)
        arr = self._data.get(cid)
        if arr is None:
            arr = []
            self._data[cid] = arr

        arr.append(MemMsg(role=str(role), content=str(content), ts=time.time()))

        # держим последние max_turns сообщений
        if len(arr) > self.max_turns:
            self._data[cid] = arr[-self.max_turns :]

    def get(self, chat_id: int) -> List[dict]:
        cid = int(chat_id)
        arr = self._data.get(cid, [])
        # возвращаем в “универсальном” формате для brain/openai
        return [{"role": m.role, "content": m.content} for m in arr]

    def clear(self, chat_id: int) -> None:
        cid = int(chat_id)
        self._data.pop(cid, None)

    def stats(self, chat_id: int) -> dict:
        cid = int(chat_id)
        n = len(self._data.get(cid, []))
        return {"items": n, "max_turns": self.max_turns}

    # --- extras (не мешают, но полезны) ---
    def dump_raw(self, chat_id: int) -> List[dict]:
        cid = int(chat_id)
        arr = self._data.get(cid, [])
        return [{"role": m.role, "content": m.content, "ts": m.ts} for m in arr]

    def set_limit(self, max_turns: int) -> None:
        try:
            v = int(max_turns)
            if v < 4:
                v = 4
            self.max_turns = v
        except Exception:
            pass
