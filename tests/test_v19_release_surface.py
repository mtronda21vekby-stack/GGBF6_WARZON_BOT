from __future__ import annotations

from pathlib import Path

from app.release import APP_VERSION, RELEASE_CONTRACT


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "webapp" / "static"


def test_v19_release_contract_and_mission_assets_are_explicit():
    assert APP_VERSION == "19.0.0"
    assert RELEASE_CONTRACT == "bco-adaptive-mission-control-v19"

    command_js = (STATIC / "command-center.js").read_text(encoding="utf-8")
    command_css = (STATIC / "command-center.css").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "MISSION CONTROL" in command_js
    assert "/webapp/api/mission" in command_js
    assert "mission" in command_css.casefold()
    assert "command-center.js" in index


def test_v19_runtime_and_deployment_gates_are_present():
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    readiness = (ROOT / "app" / "observability" / "readiness.py").read_text(encoding="utf-8")
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "bco-intelligence-ci.yml").read_text(encoding="utf-8")

    assert "ADAPTIVE_MISSION_CONTROL_ENABLED" in config
    assert "adaptive_mission_control" in readiness
    assert "ADAPTIVE_MISSION_CONTROL_ENABLED" in render
    assert "feature/bco-adaptive-mission-control-v19" in workflow
    assert "/webapp/api/mission" in workflow
