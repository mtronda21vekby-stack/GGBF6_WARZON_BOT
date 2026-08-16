# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Mapping


log = logging.getLogger("bco.storage")


class ResilientStore:
    """Primary persistent store with an in-process memory mirror/fallback.

    Writes are mirrored to fallback. Reads prefer primary and degrade to the
    fallback if the remote backend is unavailable. This keeps the bot alive
    during transient storage outages without pretending that fallback writes
    are already durable remotely.
    """

    def __init__(self, primary: Any, fallback: Any) -> None:
        self.primary = primary
        self.fallback = fallback

    def _read(self, name: str, *args, **kwargs):
        try:
            return getattr(self.primary, name)(*args, **kwargs)
        except Exception as exc:
            log.warning("storage primary read failed method=%s error=%s", name, type(exc).__name__)
            return getattr(self.fallback, name)(*args, **kwargs)

    def _write(self, name: str, *args, **kwargs) -> None:
        primary_ok = True
        try:
            getattr(self.primary, name)(*args, **kwargs)
        except Exception as exc:
            primary_ok = False
            log.warning("storage primary write failed method=%s error=%s", name, type(exc).__name__)
        try:
            getattr(self.fallback, name)(*args, **kwargs)
        except Exception as exc:
            log.warning("storage fallback write failed method=%s error=%s", name, type(exc).__name__)
        if not primary_ok:
            return

    def add(self, chat_id: int, role: str, content: Any) -> None:
        self._write("add", chat_id, role, content)

    def get(self, chat_id: int) -> list[dict]:
        return self._read("get", chat_id)

    def clear(self, chat_id: int) -> None:
        self._write("clear", chat_id)

    def stats(self, chat_id: int) -> dict:
        data = dict(self._read("stats", chat_id) or {})
        data.setdefault("backend", "resilient")
        data["fallback_backend"] = (self.fallback.stats(chat_id) or {}).get("backend", "memory")
        return data

    def get_profile(self, chat_id: int) -> dict[str, Any]:
        return dict(self._read("get_profile", chat_id) or {})

    def set_profile(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        self._write("set_profile", chat_id, patch)

    def reset_profile(self, chat_id: int) -> None:
        self._write("reset_profile", chat_id)

    def get_summary(self, chat_id: int) -> str:
        return str(self._read("get_summary", chat_id) or "")

    def set_summary(self, chat_id: int, summary: str) -> None:
        self._write("set_summary", chat_id, summary)

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        return dict(self._read("get_derived_intelligence", chat_id) or {})

    def set_derived_intelligence(self, chat_id: int, data: Mapping[str, Any]) -> None:
        self._write("set_derived_intelligence", chat_id, data)

    def add_recurring_mistake(self, chat_id: int, mistake: str) -> None:
        self._write("add_recurring_mistake", chat_id, mistake)

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return list(self._read("list_recurring_mistakes", chat_id) or [])

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        if hasattr(self.primary, "list_mistake_stats") and hasattr(self.fallback, "list_mistake_stats"):
            return list(self._read("list_mistake_stats", chat_id) or [])
        return [{"label": x, "count": 1} for x in self.list_recurring_mistakes(chat_id)]

    def add_episode(self, chat_id: int, event: Mapping[str, Any]) -> None:
        self._write("add_episode", chat_id, event)

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        return list(self._read("list_episodes", chat_id, limit) or [])

    def add_training_session(self, chat_id: int, event: Mapping[str, Any]) -> None:
        self._write("add_training_session", chat_id, event)

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        return list(self._read("list_training_sessions", chat_id) or [])

    def add_progression_event(self, chat_id: int, event: Mapping[str, Any]) -> None:
        self._write("add_progression_event", chat_id, event)

    def list_progression_events(self, chat_id: int) -> list[dict]:
        return list(self._read("list_progression_events", chat_id) or [])

    def close(self) -> None:
        for store in (self.primary, self.fallback):
            fn = getattr(store, "close", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
