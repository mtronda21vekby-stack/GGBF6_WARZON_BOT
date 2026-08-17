from app.config import Settings


def test_adaptive_mission_control_defaults_on_and_is_explicit():
    settings = Settings()
    assert hasattr(settings, "adaptive_mission_control_enabled")
    assert settings.adaptive_mission_control_enabled is True
