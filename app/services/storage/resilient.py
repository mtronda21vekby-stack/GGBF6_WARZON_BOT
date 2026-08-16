# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import inspect
import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping


log = logging.getLogger("bco.storage")


@dataclass(frozen=True)
class PendingWrite:
    operation_id: str
    method: str
    args: tuple
    kwargs: dict


class ResilientStore:
    """Persistent primary + memory mirror + bounded FIFO write recovery.

    Once a primary write fails, later writes remain ordered behind it. Appends
    receive stable operation IDs so replay after ambiguous network failures is
    idempotent when the primary adapter supports operation_id.

    The outbox is intentionally in-process: it recovers transient outages while
    this service instance remains alive. It is not described as durable across
    a process/container restart.
    """

    def __init__(self, primary: Any, fallback: Any, *, outbox_max: int = 500, replay_batch: int = 50) -> None:
        self.primary = primary
        self.fallback = fallback
        self.outbox_max = max(10, int(outbox_max or 500))
        self.replay_batch = max(1, min(int(replay_batch or 50), self.outbox_max))
        self._pending: deque[PendingWrite] = deque()
        self._lock = threading.RLock()
        self._primary_available = True
        self._last_primary_error = ""
        self._replayed = 0
        self._dropped = 0

    @staticmethod
    def _new_operation_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _supports_operation_id(fn: Any) -> bool:
        try:
            params = inspect.signature(fn).parameters.values()
            return any(p.name == "operation_id" or p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        except Exception:
            return False

    def _primary_call(self, op: PendingWrite):
        fn = getattr(self.primary, op.method)
        if self._supports_operation_id(fn):
            return fn(*op.args, **op.kwargs, operation_id=op.operation_id)
        return fn(*op.args, **op.kwargs)

    def _remember_failure(self, method: str, exc: Exception) -> None:
        self._primary_available = False
        self._last_primary_error = type(exc).__name__
        log.warning("storage primary failed method=%s error=%s", method, self._last_primary_error)

    def _enqueue_locked(self, op: PendingWrite) -> None:
        if len(self._pending) >= self.outbox_max:
            self._dropped += 1
            log.error(
                "storage recovery outbox full method=%s pending=%d dropped=%d",
                op.method, len(self._pending), self._dropped,
            )
            return
        self._pending.append(op)

    def _flush_locked(self) -> int:
        replayed_now = 0
        while self._pending and replayed_now < self.replay_batch:
            op = self._pending[0]
            try:
                self._primary_call(op)
            except Exception as exc:
                self._remember_failure(op.method, exc)
                break
            self._pending.popleft()
            self._replayed += 1
            replayed_now += 1
            self._primary_available = True
            self._last_primary_error = ""
        if replayed_now:
            log.info("storage recovery replayed=%d pending=%d", replayed_now, len(self._pending))
        return replayed_now

    def _read(self, name: str, *args, **kwargs):
        with self._lock:
            if self._pending:
                self._flush_locked()
                if self._pending:
                    return getattr(self.fallback, name)(*args, **kwargs)
            try:
                value = getattr(self.primary, name)(*args, **kwargs)
                self._primary_available = True
                self._last_primary_error = ""
                return value
            except Exception as exc:
                self._remember_failure(name, exc)
                return getattr(self.fallback, name)(*args, **kwargs)

    def _write(self, name: str, *args, **kwargs) -> None:
        # Capture immutable-enough snapshots before caller-owned dicts can be
        # mutated after the request returns.
        try:
            frozen_args = tuple(copy.deepcopy(args))
            frozen_kwargs = dict(copy.deepcopy(kwargs))
        except Exception:
            frozen_args = tuple(args)
            frozen_kwargs = dict(kwargs)
        op = PendingWrite(self._new_operation_id(), name, frozen_args, frozen_kwargs)

        with self._lock:
            try:
                getattr(self.fallback, name)(*args, **kwargs)
            except Exception as exc:
                log.warning("storage fallback write failed method=%s error=%s", name, type(exc).__name__)

            if self._pending:
                self._flush_locked()
                if self._pending:
                    self._enqueue_locked(op)
                    return

            try:
                self._primary_call(op)
                self._primary_available = True
                self._last_primary_error = ""
            except Exception as exc:
                self._remember_failure(name, exc)
                self._enqueue_locked(op)

    # Working memory -------------------------------------------------
    def add(self, chat_id: int, role: str, content: Any) -> None:
        self._write("add", chat_id, role, content)

    def get(self, chat_id: int) -> list[dict]:
        return self._read("get", chat_id)

    def clear(self, chat_id: int) -> None:
        self._write("clear", chat_id)

    def stats(self, chat_id: int) -> dict:
        data = dict(self._read("stats", chat_id) or {})
        try:
            fallback_stats = self.fallback.stats(chat_id) or {}
        except Exception:
            fallback_stats = {}
        with self._lock:
            data["backend"] = "resilient"
            data["primary_backend"] = data.get("primary_backend") or "supabase"
            data["fallback_backend"] = fallback_stats.get("backend", "memory")
            data["primary_available"] = self._primary_available
            data["outbox_pending"] = len(self._pending)
            data["outbox_replayed"] = self._replayed
            data["outbox_dropped"] = self._dropped
            data["last_primary_error"] = self._last_primary_error
        return data

    # Player profile -------------------------------------------------
    def get_profile(self, chat_id: int) -> dict[str, Any]:
        return dict(self._read("get_profile", chat_id) or {})

    def set_profile(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        self._write("set_profile", chat_id, patch)

    def reset_profile(self, chat_id: int) -> None:
        self._write("reset_profile", chat_id)

    # Summary / derived ---------------------------------------------
    def get_summary(self, chat_id: int) -> str:
        return str(self._read("get_summary", chat_id) or "")

    def set_summary(self, chat_id: int, summary: str) -> None:
        self._write("set_summary", chat_id, summary)

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        return dict(self._read("get_derived_intelligence", chat_id) or {})

    def set_derived_intelligence(self, chat_id: int, data: Mapping[str, Any]) -> None:
        self._write("set_derived_intelligence", chat_id, data)

    # Mistakes -------------------------------------------------------
    def add_recurring_mistake(self, chat_id: int, mistake: str) -> None:
        self._write("add_recurring_mistake", chat_id, mistake)

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return list(self._read("list_recurring_mistakes", chat_id) or [])

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        if hasattr(self.primary, "list_mistake_stats") and hasattr(self.fallback, "list_mistake_stats"):
            return list(self._read("list_mistake_stats", chat_id) or [])
        return [{"label": x, "count": 1} for x in self.list_recurring_mistakes(chat_id)]

    # Episodes / training / progression -----------------------------
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

    def recovery_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "primary_available": self._primary_available,
                "outbox_pending": len(self._pending),
                "outbox_replayed": self._replayed,
                "outbox_dropped": self._dropped,
                "last_primary_error": self._last_primary_error,
                "outbox_max": self.outbox_max,
            }

    def close(self) -> None:
        with self._lock:
            if self._pending:
                self._flush_locked()
        for store in (self.primary, self.fallback):
            fn = getattr(store, "close", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
