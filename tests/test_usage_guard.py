from __future__ import annotations

from types import SimpleNamespace

from app.security.usage_guard import GuardRule, UpdateReplayGuard, UsageGuard, WindowLimit
from app.services.conversation.service import ConversationService


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


def _guard(clock: Clock, *, subject_max: int = 2, global_max: int = 3, max_buckets: int = 128) -> UsageGuard:
    return UsageGuard(
        enabled=True,
        clock=clock,
        max_buckets=max_buckets,
        rules={
            "ai": GuardRule(
                subject_limits=(WindowLimit(subject_max, 60),),
                global_limits=(WindowLimit(global_max, 60),),
            )
        },
    )


def test_usage_guard_enforces_subject_and_global_windows():
    clock = Clock()
    guard = _guard(clock)

    assert guard.check(1, "ai").allowed is True
    assert guard.check(1, "ai").allowed is True

    subject_block = guard.check(1, "ai")
    assert subject_block.allowed is False
    assert subject_block.scope == "subject"
    assert subject_block.retry_after_s == 60

    assert guard.check(2, "ai").allowed is True
    global_block = guard.check(3, "ai")
    assert global_block.allowed is False
    assert global_block.scope == "global"

    clock.advance(61)
    assert guard.check(1, "ai").allowed is True

    snapshot = guard.snapshot()
    assert snapshot["allowed"]["ai"] == 4
    assert snapshot["blocked"]["ai"] == 2
    assert "subject:1" not in repr(snapshot)


def test_usage_guard_global_budget_survives_subject_bucket_churn():
    clock = Clock()
    guard = _guard(clock, subject_max=1000, global_max=5, max_buckets=128)

    for chat_id in range(5):
        assert guard.check(chat_id, "ai").allowed is True

    for chat_id in range(1000, 1200):
        decision = guard.check(chat_id, "ai")
        assert decision.allowed is False
        assert decision.scope == "global"

    assert guard.snapshot()["active_buckets"] <= 128


def test_factory_keeps_stt_and_tts_as_independent_cost_boundaries():
    settings = SimpleNamespace(
        usage_guard_enabled=True,
        usage_guard_max_buckets=128,
        stt_rate_limit_1m=1,
        stt_rate_limit_1h=10,
        stt_global_rate_limit_1m=100,
        stt_global_rate_limit_1h=1000,
        voice_rate_limit_1m=1,
        voice_rate_limit_1h=10,
        voice_global_rate_limit_1m=100,
        voice_global_rate_limit_1h=1000,
    )
    guard = UsageGuard.from_settings(settings)

    assert guard.check(77, "stt").allowed is True
    assert guard.check(77, "stt").allowed is False
    # Exhausting transcription must not block one separate TTS request.
    assert guard.check(77, "voice").allowed is True
    assert guard.check(77, "voice").allowed is False

    snapshot = guard.snapshot()
    assert "stt" in snapshot["categories"]
    assert "voice" in snapshot["categories"]


def test_update_replay_guard_deduplicates_then_expires():
    clock = Clock()
    replay = UpdateReplayGuard(ttl_s=30, max_entries=128, clock=clock)

    assert replay.accept(9001) is True
    assert replay.accept(9001) is False
    assert replay.snapshot()["duplicates"] == 1

    clock.advance(31)
    assert replay.accept(9001) is True


def test_disabled_usage_guard_never_blocks():
    clock = Clock()
    guard = UsageGuard(
        enabled=False,
        clock=clock,
        rules={"ai": GuardRule(subject_limits=(WindowLimit(1, 60),))},
    )
    for _ in range(100):
        assert guard.check(1, "ai").allowed is True


class FakeProfiles:
    def is_trusted_context(self, profile):
        return profile.get("_context_token") == "trusted"


class FakeBrain:
    def __init__(self) -> None:
        self.calls = 0

    def reply(self, **kwargs):
        self.calls += 1
        return "analysis-ok"


def test_conversation_guard_blocks_before_brain_generation():
    clock = Clock()
    guard = _guard(clock, subject_max=1, global_max=100)
    brain = FakeBrain()
    conversation = ConversationService(
        brain=brain,
        profiles=FakeProfiles(),
        usage_guard=guard,
    )
    profile = {"_chat_id": 77, "_context_token": "trusted"}

    assert conversation.reply(text="first", profile=profile, history=[]) == "analysis-ok"
    blocked = conversation.reply(text="second", profile=profile, history=[])
    assert "Слишком много AI-запросов" in blocked
    assert brain.calls == 1
