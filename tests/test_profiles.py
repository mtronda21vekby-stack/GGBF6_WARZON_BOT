from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


def test_legacy_defaults_remain():
    service = ProfileService(InMemoryStore())
    profile = service.get(1)
    assert profile["game"] == "Warzone"
    assert profile["voice"] == "TEAMMATE"
    assert profile["difficulty"] == "Normal"


def test_new_player_fields_do_not_get_invented_defaults():
    service = ProfileService(InMemoryStore())
    intel = service.get_intelligence(1).to_dict()
    assert "rank" not in intel
    assert "kd" not in intel


def test_patch_keeps_extended_fields():
    service = ProfileService(InMemoryStore())
    service.patch(1, {"rank": "Diamond", "current_goal": "Iridescent"})
    profile = service.get(1)
    assert profile["rank"] == "Diamond"
    assert profile["current_goal"] == "Iridescent"
