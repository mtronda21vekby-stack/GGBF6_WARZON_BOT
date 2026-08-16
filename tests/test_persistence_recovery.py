from __future__ import annotations

import json

import httpx

from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


class FakeIdempotentPrimary:
    def __init__(self):
        self.messages = []
        self.seen = set()
        self.mistake_receipts = set()
        self.mistakes = {}
        self.down = False
        self.raise_after_commit_once = False

    def _gate(self):
        if self.down:
            raise TimeoutError("primary down")

    def add(self, chat_id, role, content, *, operation_id=None):
        self._gate()
        if operation_id not in self.seen:
            self.seen.add(operation_id)
            self.messages.append({"role": role, "content": str(content)})
        if self.raise_after_commit_once:
            self.raise_after_commit_once = False
            raise TimeoutError("response lost after commit")

    def get(self, chat_id):
        self._gate()
        return list(self.messages)

    def clear(self, chat_id, *, operation_id=None):
        self._gate()
        self.messages.clear()

    def add_recurring_mistake(self, chat_id, mistake, *, operation_id=None):
        self._gate()
        if operation_id in self.mistake_receipts:
            return
        self.mistake_receipts.add(operation_id)
        self.mistakes[mistake] = self.mistakes.get(mistake, 0) + 1
        if self.raise_after_commit_once:
            self.raise_after_commit_once = False
            raise TimeoutError("response lost after mistake commit")

    def list_recurring_mistakes(self, chat_id):
        self._gate()
        return list(self.mistakes)

    def list_mistake_stats(self, chat_id):
        self._gate()
        return [{"label": k, "count": v} for k, v in self.mistakes.items()]

    def stats(self, chat_id):
        self._gate()
        return {"backend": "fake-primary", "turns": len(self.messages)}

    def close(self):
        return None


def test_ambiguous_message_commit_replays_exactly_once():
    primary = FakeIdempotentPrimary()
    primary.raise_after_commit_once = True
    store = ResilientStore(primary, InMemoryStore(), outbox_max=20, replay_batch=20)

    store.add(1, "user", "hello")
    assert store.recovery_status()["outbox_pending"] == 1
    assert len(primary.messages) == 1  # remote commit happened before timeout

    rows = store.get(1)  # recovery flush
    assert rows == [{"role": "user", "content": "hello"}]
    assert len(primary.messages) == 1  # operation_id prevented duplicate
    status = store.recovery_status()
    assert status["outbox_pending"] == 0
    assert status["outbox_replayed"] == 1
    assert status["primary_available"] is True


def test_outage_preserves_clear_then_add_fifo_order():
    primary = FakeIdempotentPrimary()
    primary.messages = [{"role": "user", "content": "old"}]
    fallback = InMemoryStore()
    fallback.add(9, "user", "old")
    store = ResilientStore(primary, fallback, outbox_max=20, replay_batch=20)

    primary.down = True
    store.clear(9)
    store.add(9, "user", "new")
    assert store.get(9) == [{"role": "user", "content": "new"}]
    assert store.recovery_status()["outbox_pending"] == 2

    primary.down = False
    rows = store.get(9)
    assert rows == [{"role": "user", "content": "new"}]
    assert primary.messages == [{"role": "user", "content": "new"}]
    assert store.recovery_status()["outbox_pending"] == 0


def test_ambiguous_mistake_increment_is_exactly_once():
    primary = FakeIdempotentPrimary()
    primary.raise_after_commit_once = True
    store = ResilientStore(primary, InMemoryStore(), outbox_max=20, replay_batch=20)

    store.add_recurring_mistake(5, "Late rotation")
    assert primary.mistakes["Late rotation"] == 1
    assert store.recovery_status()["outbox_pending"] == 1

    stats = store.list_mistake_stats(5)
    assert stats[0]["count"] == 1
    assert primary.mistakes["Late rotation"] == 1
    assert store.recovery_status()["outbox_pending"] == 0


def test_supabase_append_uses_operation_id_conflict_target():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["prefer"] = request.headers.get("prefer")
        seen["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201, json=[])

    store = SupabaseStore(url="https://example.supabase.co", service_role_key="secret")
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    try:
        store.add(7, "user", "hello", operation_id="op_1234567890")
    finally:
        store.close()

    assert "on_conflict=operation_id" in seen["url"]
    assert "ignore-duplicates" in seen["prefer"]
    assert seen["json"]["operation_id"] == "op_1234567890"


def test_supabase_mistake_replay_uses_once_rpc():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=True)

    store = SupabaseStore(url="https://example.supabase.co", service_role_key="secret")
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    try:
        store.add_recurring_mistake(7, "Late rotation", operation_id="op_mistake_123")
    finally:
        store.close()

    assert seen["path"].endswith("/rpc/bco_record_mistake_once")
    assert seen["json"]["p_operation_id"] == "op_mistake_123"


def test_supabase_episode_rows_are_normalized_for_command_center():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "kind": "vod_sampled_frames",
            "data": {"analysis": {"summary": "evidence"}, "confirmed_mistakes": ["overpeek"]},
            "created_at": "2026-08-16T00:00:00Z",
        }])

    store = SupabaseStore(url="https://example.supabase.co", service_role_key="secret")
    old = store._client
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    old.close()
    try:
        rows = store.list_episodes(7)
    finally:
        store.close()

    assert rows[0]["kind"] == "vod_sampled_frames"
    assert rows[0]["analysis"]["summary"] == "evidence"
    assert rows[0]["confirmed_mistakes"] == ["overpeek"]
