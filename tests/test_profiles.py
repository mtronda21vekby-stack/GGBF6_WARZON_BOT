from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


def test_current_defaults_remain():
    service = ProfileService(InMemoryStore())
    profile = service.get(1)
    assert profile["game"] == "Warzone"
    assert profile["voice"] == "TEAMMATE"
    assert profile["difficulty"] == "Normal"
    assert profile["voice_identity"] == "female"
    assert profile["tts_voice"] == "marin"


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


def test_mode_aliases_stay_synchronized_for_legacy_and_new_brains():
    service = ProfileService(InMemoryStore())
    service.patch(1, {"difficulty": "Demon", "voice": "COACH"})
    profile = service.get(1)
    intelligence = service.get_intelligence(1).to_dict()

    assert profile["difficulty"] == "Demon"
    assert profile["brain_mode"] == "Demon"
    assert profile["voice"] == "COACH"
    assert profile["voice_mode"] == "COACH"
    assert intelligence["difficulty"] == "Demon"
    assert intelligence["brain_mode"] == "Demon"
    assert intelligence["voice"] == "COACH"
    assert intelligence["voice_mode"] == "COACH"


def test_voice_tts_and_zombies_runtime_fields_survive_intelligence_projection():
    service = ProfileService(InMemoryStore())
    service.patch(
        1,
        {
            "tts_mode": "auto",
            "tts_voice": "marin",
            "zombies_map": "Astra",
            "bf6_class": "Recon",
        },
    )
    intelligence = service.get_intelligence(1).to_dict()

    assert intelligence["tts_mode"] == "auto"
    assert intelligence["tts_voice"] == "marin"
    assert intelligence["zombies_map"] == "Astra"
    assert intelligence["bf6_class"] == "Recon"
