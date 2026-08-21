# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryStore:
    """Production-compatible in-process fallback implementing the full Storage API."""

    def __init__(self, memory_max_turns: int = 20, *args, **kwargs):
        raw = kwargs.get("max_turns", memory_max_turns)
        try:
            self.memory_max_turns = max(4, int(raw))
        except Exception:
            self.memory_max_turns = 20

        self._history: dict[int, list[dict]] = defaultdict(list)
        self._profiles: dict[int, dict[str, Any]] = {}
        self._summaries: dict[int, str] = {}
        self._derived: dict[int, dict[str, Any]] = {}
        self._mistakes: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._episodes: dict[int, list[dict]] = defaultdict(list)
        self._training: dict[int, list[dict]] = defaultdict(list)
        self._progression: dict[int, list[dict]] = defaultdict(list)

    # Canonical identity ---------------------------------------------
    def resolve_telegram_identity(self, telegram_user_id: int) -> dict[str, Any]:
        # The in-process fallback never manufactures canonical accounts.
        return {}

    # Working memory -------------------------------------------------
    def add(self, chat_id: int, role: str, content: Any) -> None:
        cid = int(chat_id)
        self._history[cid].append({"role": str(role), "content": str(content), "created_at": _now_iso()})
        max_msgs = self.memory_max_turns * 2
        if len(self._history[cid]) > max_msgs:
            self._history[cid] = self._history[cid][-max_msgs:]

    def get(self, chat_id: int) -> list[dict]:
        return [{"role": x.get("role", ""), "content": x.get("content", "")} for x in self._history.get(int(chat_id), [])]

    def clear(self, chat_id: int) -> None:
        """Clear only short-term conversation memory (legacy button semantics)."""
        self._history.pop(int(chat_id), None)

    # Player profile -------------------------------------------------
    def get_profile(self, chat_id: int) -> dict[str, Any]:
        return dict(self._profiles.get(int(chat_id), {}))

    def set_profile(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        cur = self._profiles.setdefault(cid, {})
        for key, value in (patch or {}).items():
            cur[str(key)] = value

    def reset_profile(self, chat_id: int) -> None:
        self._profiles.pop(int(chat_id), None)

    # Summary / derived ---------------------------------------------
    def get_summary(self, chat_id: int) -> str:
        return self._summaries.get(int(chat_id), "")

    def set_summary(self, chat_id: int, summary: str) -> None:
        self._summaries[int(chat_id)] = str(summary or "").strip()

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        return dict(self._derived.get(int(chat_id), {}))

    def set_derived_intelligence(self, chat_id: int, data: Mapping[str, Any]) -> None:
        self._derived[int(chat_id)] = dict(data or {})

    # Mistakes -------------------------------------------------------
    def add_recurring_mistake(self, chat_id: int, mistake: str) -> None:
        cid = int(chat_id)
        label = str(mistake or "").strip()
        if not label:
            return
        key = " ".join(label.lower().split())
        row = self._mistakes[cid].get(key)
        now = _now_iso()
        if row is None:
            self._mistakes[cid][key] = {
                "mistake_key": key,
                "label": label,
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "evidence": {},
            }
        else:
            row["count"] = int(row.get("count", 0)) + 1
            row["last_seen"] = now
            row["label"] = label

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        rows = [dict(x) for x in self._mistakes.get(int(chat_id), {}).values()]
        rows.sort(key=lambda x: (int(x.get("count", 0)), str(x.get("last_seen", ""))), reverse=True)
        return rows[:20]

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return [str(x.get("label") or "") for x in self.list_mistake_stats(chat_id) if x.get("label")]

    # Episodes / training / progression -----------------------------
    def add_episode(self, chat_id: int, event: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        item = dict(event or {})
        item.setdefault("created_at", _now_iso())
        self._episodes[cid].append(item)
        self._episodes[cid] = self._episodes[cid][-100:]

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        n = max(1, min(int(limit or 20), 100))
        return [dict(x) for x in reversed(self._episodes.get(int(chat_id), [])[-n:])]

    def add_training_session(self, chat_id: int, event: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        item = dict(event or {})
        item.setdefault("created_at", _now_iso())
        self._training[cid].append(item)
        self._training[cid] = self._training[cid][-50:]

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        return [dict(x) for x in reversed(self._training.get(int(chat_id), []))]

    def add_progression_event(self, chat_id: int, event: Mapping[str, Any]) -> None:
        cid = int(chat_id)
        item = dict(event or {})
        item.setdefault("created_at", _now_iso())
        self._progression[cid].append(item)
        self._progression[cid] = self._progression[cid][-100:]

    def list_progression_events(self, chat_id: int) -> list[dict]:
        return [dict(x) for x in reversed(self._progression.get(int(chat_id), []))]

    # Lifecycle / stats ---------------------------------------------
    def purge_player(self, chat_id: int) -> None:
        cid = int(chat_id)
        self._history.pop(cid, None)
        self._profiles.pop(cid, None)
        self._summaries.pop(cid, None)
        self._derived.pop(cid, None)
        self._mistakes.pop(cid, None)
        self._episodes.pop(cid, None)
        self._training.pop(cid, None)
        self._progression.pop(cid, None)

    def stats(self, chat_id: int) -> dict:
        cid = int(chat_id)
        return {
            "turns": len(self._history.get(cid, [])),
            "max_turns": self.memory_max_turns,
            "has_profile": cid in self._profiles,
            "has_summary": bool(self._summaries.get(cid)),
            "recurring_mistakes": len(self._mistakes.get(cid, {})),
            "training_sessions": len(self._training.get(cid, [])),
            "progression_events": len(self._progression.get(cid, [])),
            "episodes": len(self._episodes.get(cid, [])),
            "backend": "memory",
        }

    def close(self) -> None:
        return None
