from app.services.conversation.service import ConversationService
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


class DummyBrain:
    def __init__(self):
        self.last_context = None

    def reply(self, *, text, profile, history, player_context=None):
        self.last_context = dict(player_context or {})
        return "OK"


def test_trusted_conversation_builds_long_term_player_intelligence():
    store = InMemoryStore()
    profiles = ProfileService(store)
    brain = DummyBrain()
    conversation = ConversationService(brain=brain, store=store, profiles=profiles)

    profile = profiles.get(42)
    conversation.reply(
        text="КД 1.25. Цель: улучшить ротации. Поздно сделал ротацию. 6 kills, топ 5.",
        profile=profile,
        history=[],
    )

    saved = store.get_profile(42)
    assert saved["kd"] == 1.25
    assert saved["current_goal"].startswith("улучшить ротации")
    assert store.list_mistake_stats(42)[0]["label"] == "Поздняя ротация"
    assert store.list_mistake_stats(42)[0]["count"] == 1
    assert store.list_progression_events(42)[0]["metrics"]["kills"] == 6
    assert store.list_progression_events(42)[0]["metrics"]["placement"] == 5
    assert "Повторяющиеся ошибки" in store.get_summary(42)

    # The next request receives persistent context from the previous observation.
    conversation.reply(text="Что мне исправлять?", profile=profiles.get(42), history=[])
    assert brain.last_context["top_mistakes"][0]["label"] == "Поздняя ротация"
    assert brain.last_context["memory_summary"]


def test_repeated_mistake_increments_evidence_count():
    store = InMemoryStore()
    profiles = ProfileService(store)
    conversation = ConversationService(brain=DummyBrain(), store=store, profiles=profiles)

    for _ in range(3):
        conversation.reply(
            text="Опять поздно сделал ротацию и умер в газе",
            profile=profiles.get(5),
            history=[],
        )

    assert store.list_mistake_stats(5)[0]["count"] == 3


def test_forged_client_profile_cannot_mutate_persistent_memory():
    store = InMemoryStore()
    profiles = ProfileService(store)
    conversation = ConversationService(brain=DummyBrain(), store=store, profiles=profiles)

    forged = {
        "game": "Warzone",
        "_chat_id": 999,
        "_context_token": "forged",
    }
    conversation.reply(
        text="КД 9.9. Поздно сделал ротацию. 50 kills топ 1",
        profile=forged,
        history=[],
    )

    assert store.get_profile(999) == {}
    assert store.list_recurring_mistakes(999) == []
    assert store.list_progression_events(999) == []


def test_full_profile_reset_purges_player_intelligence():
    store = InMemoryStore()
    profiles = ProfileService(store)
    store.set_profile(7, {"rank": "Diamond"})
    store.add(7, "user", "hello")
    store.add_recurring_mistake(7, "late rotation")
    store.add_progression_event(7, {"kills": 4})
    store.set_summary(7, "summary")

    profiles.reset(7)

    assert store.get(7) == []
    assert store.get_profile(7) == {}
    assert store.list_recurring_mistakes(7) == []
    assert store.list_progression_events(7) == []
    assert store.get_summary(7) == ""
