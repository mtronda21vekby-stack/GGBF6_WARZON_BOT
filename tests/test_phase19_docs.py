from pathlib import Path


def test_phase19_docs_define_release_and_rollback():
    root = Path(__file__).resolve().parents[1]
    phase = (root / "docs/PHASE19_ADAPTIVE_MISSION_CONTROL.md").read_text(encoding="utf-8")
    runbook = (root / "docs/PHASE19_PRODUCTION_RUNBOOK.md").read_text(encoding="utf-8")
    assert "19.0.0 / bco-adaptive-mission-control-v19" in phase
    assert "ADAPTIVE_MISSION_CONTROL_ENABLED=0" in phase
    assert "ADAPTIVE_MISSION_CONTROL_ENABLED=0" in runbook
    assert "No database rollback is required" in runbook
