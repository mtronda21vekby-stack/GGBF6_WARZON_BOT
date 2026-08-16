from app.services.conversation.service import ConversationService
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


class Brain:
    def reply(self, *, text, profile, history, player_context=None):
        return "reply"


def test_verified_miniapp_style_call_records_working_pair():
    store = InMemoryStore()
    profiles = ProfileService(store)
    service = ConversationService(brain=Brain(), store=store, profiles=profiles)

    service.reply(text="hello", profile=profiles.get(1), history=[])
    assert store.get(1) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "reply"},
    ]


def test_telegram_style_call_does_not_duplicate_router_managed_history():
    store = InMemoryStore()
    profiles = ProfileService(store)
    service = ConversationService(brain=Brain(), store=store, profiles=profiles)

    store.add(2, "user", "hello")  # Router does this before ConversationService
    history = store.get(2)
    service.reply(text="hello", profile=profiles.get(2), history=history)

    assert store.get(2) == [{"role": "user", "content": "hello"}]
