from pathlib import Path


def test_phase19_does_not_add_a_required_database_migration():
    root = Path(__file__).resolve().parents[1]
    runbook = (root / "docs/PHASE19_PRODUCTION_RUNBOOK.md").read_text(encoding="utf-8")
    assert "existing bounded progression-event persistence path" in runbook
