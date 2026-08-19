from app.core.router import _clean_ecosystem_profile_patch
from app.services.profiles.service import DEFAULT_PROFILE, ProfileService


def test_ecosystem_profile_patch_accepts_only_supported_fields():
    patch = _clean_ecosystem_profile_patch({
        "profile": {
            "profile_name": "Operator-" + "X" * 40,
            "voice_identity": "female",
            "tts_mode": "on_demand",
            "training_focus": "positioning",
            "tts_voice": "onyx",
            "black_crown_user_id": "client-must-not-own-this",
        }
    })
    assert patch["profile_name"] == ("Operator-" + "X" * 40)[:32]
    assert patch["voice_identity"] == "female"
    assert patch["tts_voice"] == "marin"
    assert patch["tts_mode"] == "on_demand"
    assert patch["training_focus"] == "position"
    assert "black_crown_user_id" not in patch


def test_male_identity_owns_cedar_default():
    patch = _clean_ecosystem_profile_patch({"profile": {"voice_identity": "male", "tts_voice": "marin"}})
    assert patch == {"voice_identity": "male", "tts_voice": "cedar"}


def test_invalid_profile_values_fail_closed():
    patch = _clean_ecosystem_profile_patch({
        "profile": {
            "voice_identity": "celebrity",
            "tts_mode": "always_forever",
            "training_focus": "wallhack",
        }
    })
    assert patch == {}


def test_new_profile_defaults_to_female_marin():
    assert DEFAULT_PROFILE["voice_identity"] == "female"
    assert DEFAULT_PROFILE["tts_voice"] == "marin"


def test_profile_service_still_protects_canonical_identity_from_client_patch():
    clean = ProfileService._with_aliases({
        "profile_name": "KQYLN",
        "black_crown_user_id": "fake",
        "crown_identity_status": "active",
        "crown_account_status": "active",
    })
    assert clean["profile_name"] == "KQYLN"
    assert "black_crown_user_id" not in clean
    assert "crown_identity_status" not in clean
    assert "crown_account_status" not in clean
