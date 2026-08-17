from app.config import Settings
from app.release import APP_VERSION, RELEASE_CONTRACT


def test_operator_rollbacks_remain_independent_from_current_release(monkeypatch):
    monkeypatch.setenv("OPERATOR_INTELLIGENCE_ENABLED", "0")
    monkeypatch.setenv("ADAPTIVE_MISSION_CONTROL_ENABLED", "0")
    settings = Settings()
    assert APP_VERSION == "26.0.0"
    assert RELEASE_CONTRACT == "bco-causal-operator-context-v26"
    assert settings.operator_intelligence_enabled is False
    assert settings.adaptive_mission_control_enabled is False
