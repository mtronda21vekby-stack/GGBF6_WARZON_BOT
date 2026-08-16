from app.services.storage.memory import InMemoryStore


def test_working_memory_is_bounded():
    store = InMemoryStore(memory_max_turns=4)
    for i in range(20):
        store.add(1, "user", str(i))
    assert len(store.get(1)) == 8


def test_profile_is_separate_from_working_memory():
    store = InMemoryStore()
    store.set_profile(1, {"rank": "Diamond"})
    store.add(1, "user", "hello")
    store.clear(1)
    assert store.get(1) == []
    assert store.get_profile(1)["rank"] == "Diamond"


def test_episodic_namespaces_exist():
    store = InMemoryStore()
    store.add_recurring_mistake(1, "late rotation")
    store.add_training_session(1, {"focus": "aim"})
    store.add_progression_event(1, {"kd": 1.8})
    assert store.list_recurring_mistakes(1) == ["late rotation"]
    assert store.list_training_sessions(1)[0]["focus"] == "aim"
    assert store.list_progression_events(1)[0]["kd"] == 1.8
