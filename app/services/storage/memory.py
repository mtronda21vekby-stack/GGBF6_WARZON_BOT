# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping


class InMemoryStore:
    """Production-compatible fallback store.

    Working memory, profile memory, episodic events and derived intelligence are
    separate namespaces so a persistent adapter can replace this class later
    without changing Router/BrainEngine.
    """

    def __init__(self, memory_max_turns: int = 20, *args, **kwargs):
        raw = kwargs.get("max_turns", memory_max_turns)
        try:
            self.memory_max_turns = max(4, int(raw))
        except Exception:
            self.memory_max_turns = 20

        self._history: dict[int, list[dict]] = defaultdict(list)
        self._profiles: dict[int, dict[str, Any]] = {}
        self._summaries: dict[int, str] = {}
        self._mistakes: dict[int, list[str]] = defaultdict(list)
        self._training: dict[int, list[dict]] = defaultdict(list)
        self._progression: dict[int, list[dict]] = defaultdict(list)

    def add(self, chat_id: int, role: str, content: Any) -> None:
        cid = int(chat_id)
        self._history[cid].append({"role": str(role), "content": str(content)})
        max_msgs = self.memory_max_turns * 2
        if len(self._history[cid]) > max_msgs:
            self._history[cid] = self._history[cid][-max_msgs:]

    def get(self, chat_id: int) -> list[dict]:
        return [dict(x) for x in self._history.get(int(chat_id), [])]

    def clear(self, chat_id: int) -> None:
        """Clear working conversation memory only (legacy behavior)."""
        self._history.pop(int(chat_id), None)

    def stats(self, chat_id: int) -> dict:
        cid = int(chat_id)
        return {
            "turns": len(self._history.get(cid, [])),
            "max_turns": self.memory_max_turns,
            "has_profile": cid in self._profiles,
            "has_summary": bool(self._summaries.get(cid)),
            "recurring_mistakes": len(self._mistakes.get(cid, [])),
            "training_sessions": len(self._training.get(cid, [])),
            "progression_events": len(self._progression.get(cid, [])),
            "backend": "memory",
        }

    def get_profile(self, chat_id: int) -> dict[str, Any]:
        return dict(self._profiles.get(int(chat_id), {}))

    def set_profile(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        cur = self._profiles.setdefault(cid, {})
        for key, value in (patch or {}).items():
            cur[str(key)] = value

    def reset_profile(self, chat_id: int) -> None:
        self._profiles.pop(int(chat_id), None)

    def get_summary(self, chat_id: int) -> str:
        return self._summaries.get(int(chat_id), "")

    def set_summary(self, chat_id: int, summary: str) -> None:
        self._summaries[int(chat_id)] = str(summary or "").strip()

    def add_recurring_mistake(self, chat_id: int, mistake: str) -> None:
        cid = int(chat_id)
        item = str(mistake or "").strip()
        if not item:
            return
        if item not in self._mistakes[cid]:
            self._mistakes[cid].append(item)
        self._mistakes[cid] = self._mistakes[cid][-20:]

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return list(self._mistakes.get(int(chat_id), []))

    def add_training_session(self, chat_id: int, event: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        self._training[cid].append(dict(event or {}))
        self._training[cid] = self._training[cid][-50:]

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        return [dict(x) for x in self._training.get(int(chat_id), [])]

    def add_progression_event(self, chat_id: int, event: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        self._progression[cid].append(dict(event or {}))
        self._progression[cid] = self._progression[cid][-100:]

    def list_progression_events(self, chat_id: int) -> list[dict]:
        return [dict(x) for x in self._progression.get(int(chat_id), [])]
