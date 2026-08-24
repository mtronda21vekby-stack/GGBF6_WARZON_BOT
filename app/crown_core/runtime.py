from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from uuid import UUID

from app.crown_core.contracts import CrownCoreFailure


@dataclass
class ActiveTurn:
    canonical_user_id: UUID
    session_id: UUID
    turn_id: UUID
    cancellation: threading.Event = field(default_factory=threading.Event)


class ActiveTurnRegistry:
    """Bounded active-turn/cancellation authority shared by every native route."""

    def __init__(self, completed_limit: int = 256) -> None:
        self._lock = threading.RLock()
        self._active: dict[tuple[UUID, UUID], ActiveTurn] = {}
        self._completed: OrderedDict[tuple[UUID, UUID, UUID], tuple[dict, ...]] = OrderedDict()
        self._completed_limit = max(16, int(completed_limit))

    def start(self, canonical_user_id: UUID, session_id: UUID, turn_id: UUID) -> ActiveTurn:
        key = (session_id, turn_id)
        with self._lock:
            existing = self._active.get(key)
            if existing is not None:
                if existing.canonical_user_id != canonical_user_id:
                    raise CrownCoreFailure("ownership_mismatch")
                raise CrownCoreFailure("turn_in_progress")
            control = ActiveTurn(canonical_user_id, session_id, turn_id)
            self._active[key] = control
            return control

    def cancel(self, canonical_user_id: UUID, session_id: UUID, turn_id: UUID) -> bool:
        with self._lock:
            control = self._active.get((session_id, turn_id))
            if control is None:
                return False
            if control.canonical_user_id != canonical_user_id:
                raise CrownCoreFailure("ownership_mismatch")
            control.cancellation.set()
            return True

    def finish(self, control: ActiveTurn, events: list[dict] | None = None) -> None:
        key = (control.session_id, control.turn_id)
        with self._lock:
            if self._active.get(key) is control:
                self._active.pop(key, None)
            if events and not control.cancellation.is_set():
                completed_key = (control.canonical_user_id, control.session_id, control.turn_id)
                self._completed[completed_key] = tuple(dict(event) for event in events)
                self._completed.move_to_end(completed_key)
                while len(self._completed) > self._completed_limit:
                    self._completed.popitem(last=False)

    def replay(self, canonical_user_id: UUID, session_id: UUID, turn_id: UUID) -> tuple[dict, ...] | None:
        with self._lock:
            value = self._completed.get((canonical_user_id, session_id, turn_id))
            return tuple(dict(event) for event in value) if value is not None else None


class MutationReplayRegistry:
    """Small process-local idempotency cache for bounded native mutations."""

    def __init__(self, limit: int = 256) -> None:
        self._lock = threading.RLock()
        self._items: OrderedDict[tuple[UUID, UUID, str], dict] = OrderedDict()
        self._inflight: set[tuple[UUID, UUID, str]] = set()
        self._limit = max(16, int(limit))

    def begin(self, canonical_user_id: UUID, key: UUID, operation: str) -> tuple[str, dict | None]:
        cache_key = (canonical_user_id, key, operation)
        with self._lock:
            value = self._items.get(cache_key)
            if value is not None:
                return "replay", dict(value)
            if cache_key in self._inflight:
                return "in_progress", None
            self._inflight.add(cache_key)
            return "claimed", None

    def finish(self, canonical_user_id: UUID, key: UUID, operation: str, result: dict) -> None:
        cache_key = (canonical_user_id, key, operation)
        with self._lock:
            self._inflight.discard(cache_key)
            self._items[cache_key] = dict(result)
            self._items.move_to_end(cache_key)
            while len(self._items) > self._limit:
                self._items.popitem(last=False)

    def abort(self, canonical_user_id: UUID, key: UUID, operation: str) -> None:
        with self._lock:
            self._inflight.discard((canonical_user_id, key, operation))
