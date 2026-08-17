from pathlib import Path


def test_render_config_enables_adaptive_mission_control():
    root = Path(__file__).resolve().parents[1]
    rendered = (root / "render.yaml").read_text(encoding="utf-8")
    assert "ADAPTIVE_MISSION_CONTROL_ENABLED" in rendered
