from app.config import Settings
from app.release import APP_VERSION, RELEASE_CONTRACT


def test_operator_rollbacks_remain_independent_from_current_release(monkeypatch):
    monkeypatch.setenv("OPERATOR_INTELLIGENCE_ENABLED", "0")
    monkeypatch.setenv("ADAPTIVE_MISSION_CONTROL_ENABLED", "0")
    monkeypatch.setenv("MISSION_VOD_EVIDENCE_FUSION_ENABLED", "0")
    monkeypatch.setenv("OPERATOR_LONGITUDINAL_INTELLIGENCE_ENABLED", "0")
    monkeypatch.setenv("PREMIUM_DEEP_HISTORY_ENABLED", "0")
    monkeypatch.setenv("PREMIUM_ADAPTIVE_STRATEGY_ENABLED", "0")
    monkeypatch.setenv("EVIDENCE_FRESHNESS_ENABLED", "0")
    monkeypatch.setenv("REGIME_CHANGE_DETECTION_ENABLED", "0")
    monkeypatch.setenv("MISSION_ORCHESTRATOR_ENABLED", "0")
    settings = Settings()
    assert APP_VERSION == "43.0.1"
    assert RELEASE_CONTRACT == "bco-personal-meta-baseline-v43.0.1"
    assert settings.operator_intelligence_enabled is False
    assert settings.adaptive_mission_control_enabled is False
    assert settings.mission_vod_evidence_fusion_enabled is False
