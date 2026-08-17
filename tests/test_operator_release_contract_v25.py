from app.config import Settings
from app.release import APP_VERSION, RELEASE_CONTRACT


def test_v25_release_contract_and_rollback_flags(monkeypatch):
    monkeypatch.setenv("OPERATOR_INTELLIGENCE_ENABLED", "0")
    monkeypatch.setenv("ADAPTIVE_MISSION_CONTROL_ENABLED", "0")
    settings = Settings()
    assert APP_VERSION == "25.0.0"
    assert RELEASE_CONTRACT == "bco-operator-twin-missions-v25"
    assert settings.operator_intelligence_enabled is False
    assert settings.adaptive_mission_control_enabled is False
