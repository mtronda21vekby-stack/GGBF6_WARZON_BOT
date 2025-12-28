# app/services/brain/memory.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Dict, List, Any, Optional


class InMemoryStore:
    """
    RAM-память (на Render сбрасывается при перезапуске).
    Совместима с любыми вызовами:
      - InMemoryStore(memory_max_turns=20)
      - InMemoryStore(max_turns=20)
      - InMemoryStore(limit=20)
      - InMemoryStore(20)
    """

    def __init__(
        self,
        memory_max_turns: Optional[int] = None,
        *args,
        **kwargs,
    ):
        # 1) приоритет: явный memory_max_turns
        limit = memory_max_turns

        # 2) если не задан — пробуем другие имена
        if limit is None:
            for k in ("max_turns", "limit", "max_messages", "memory_limit"):
                if k in kwargs and kwargs[k] is not None:
                    limit = kwargs[k]
                    break

        # 3) если всё ещё None — пробуем позиционный
        if limit is None and len(args) >= 1 and args[0] is not None:
            limit = args[0]

        # 4) дефолт + защита
        try:
            self.max_turns = int(limit) if limit is not None else 20
        except Exception:
            self.max_turns = 20
        if self.max_turns < 4:
            self.max_turns = 4

        self._data: Dict[int, List[dict]] = {}

    def add(self, chat_id: int, role: str, content: str) -> None:
        cid = int(chat_id)
        arr = self._data.get(cid)
        if arr is None:
            arr = []
            self._data[cid] = arr

        arr.append({"role": str(role), "content": str(content), "ts": time.time()})

        if len(arr) > self.max_turns:
            self._data[cid] = arr[-self.max_turns :]

    def get(self, chat_id: int) -> List[dict]:
        cid = int(chat_id)
        arr = self._data.get(cid, [])
        # отдаём только role/content (без ts) — удобно для промпта
        return [{"role": m["role"], "content": m["content"]} for m in arr]

    def clear(self, chat_id: int) -> None:
        self._data.pop(int(chat_id), None)

    def stats(self, chat_id: int) -> dict:
        cid = int(chat_id)
        return {"items": len(self._data.get(cid, [])), "max_turns": self.max_turns}
