from pathlib import Path


def test_phase19_product_contract_exposes_one_active_mission():
    root = Path(__file__).resolve().parents[1]
    docs = (root / "docs/PHASE19_ADAPTIVE_MISSION_CONTROL.md").read_text(encoding="utf-8")
    assert "one active, measurable mission" in docs
    assert "one mission at a time" in docs
