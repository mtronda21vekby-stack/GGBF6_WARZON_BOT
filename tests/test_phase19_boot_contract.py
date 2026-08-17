from pathlib import Path


def test_v19_boot_loads_stable_base_live_layer_then_mission_control():
    root = Path(__file__).resolve().parents[1]
    boot = (root / "app/webapp/static/app.js").read_text(encoding="utf-8")
    base = boot.index("/webapp/app.base.js")
    live = boot.index("/webapp/bco.live.js")
    mission = boot.index("/webapp/command-center.js")
    assert base < live < mission
    assert "__BCO_V19_READY__" in boot
    assert "adaptive_mission_control" in boot
