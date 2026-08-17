from pathlib import Path


def test_command_center_static_surface_contains_mission_lifecycle():
    root = Path(__file__).resolve().parents[1]
    script = (root / "app/webapp/static/command-center.js").read_text(encoding="utf-8")
    style = (root / "app/webapp/static/command-center.css").read_text(encoding="utf-8")
    folded = script.casefold()
    assert "mission" in folded
    assert "accept" in folded
    assert "complete" in folded or "finish" in folded
    assert "mission" in style.casefold()
