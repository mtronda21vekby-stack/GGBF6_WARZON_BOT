# app/services/brain/memory.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class InMemoryStore:
    memory_max_turns: int = 20
    _history: Dict[int, List[dict]] = field(default_factory=dict)
    _profiles: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # --------- history ----------
    def add(self, chat_id: int, role: str, content: str) -> None:
        h = self._history.setdefault(chat_id, [])
        h.append({"role": role, "content": str(content)})
        # keep last N turns (user+assistant pairs => *2 is ok, but we store messages)
        max_msgs = max(4, int(self.memory_max_turns) * 2)
        if len(h) > max_msgs:
            self._history[chat_id] = h[-max_msgs:]

    def get(self, chat_id: int) -> List[dict]:
        return list(self._history.get(chat_id, []))

    def clear(self, chat_id: int) -> None:
        self._history.pop(chat_id, None)

    def stats(self, chat_id: int) -> dict:
        return {
            "turns": len(self._history.get(chat_id, [])),
            "max_turns": self.memory_max_turns,
            "has_profile": chat_id in self._profiles,
        }

    # --------- profile ----------
    def get_profile(self, chat_id: int) -> Dict[str, Any]:
        return dict(self._profiles.get(chat_id, {}))

    def set_profile(self, chat_id: int, patch: Dict[str, Any]) -> None:
        cur = self._profiles.setdefault(chat_id, {})
        for k, v in (patch or {}).items():
            cur[str(k)] = v

    def reset_profile(self, chat_id: int) -> None:
        self._profiles.pop(chat_id, None)
