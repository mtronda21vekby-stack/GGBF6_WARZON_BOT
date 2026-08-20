from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


STATIC = Path(__file__).resolve().parents[1] / "app" / "webapp" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_boot_coordinator_loads_stable_base_then_runtime_gated_v18_layer():
    source = _read("app.js")
    assert "/webapp/app.base.js" in source
    assert "/webapp/bco.live.js" in source
    assert "/webapp/api/runtime" in source
    assert re.search(r'method\s*:\s*"POST"', source)
    assert re.search(r"flags\.v18_overlay\s*===\s*false", source)
    assert "__BCO_RUNTIME_FLAGS__" in source


def test_live_runtime_contains_streaming_fallback_and_operator_surfaces():
    source = _read("bco.live.js")
    assert 'const STREAM_PATH = "/webapp/api/ask/stream"' in source
    assert 'const FALLBACK_PATH = "/webapp/api/ask"' in source
    assert "application/x-ndjson" in source
    assert "bco-boot-sequence" in source
    assert "bco-command-palette" in source
    assert "HapticFeedback" in source
    assert "disableVerticalSwipes" in source
    assert "localStorage" in source
    assert "navigator.onLine" in source


def test_cinematic_css_uses_technical_graphite_cyan_system_and_low_power_mode():
    source = _read("bco.cinematic.css")
    assert "--accent: #22d3ee" in source
    assert ".bco-boot-sequence" in source
    assert ".bco-telemetry-rail" in source
    assert ".bco-command-palette" in source
    assert ".bubble.is-streaming" in source
    assert "html.bco-low-power" in source
    assert "prefers-reduced-motion" in source
    assert "casino" not in source.casefold()


@pytest.mark.parametrize("name", ["app.js", "app.base.js", "bco.live.js"])
def test_webapp_javascript_passes_node_syntax_check(name: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    result = subprocess.run(
        [node, "--check", str(STATIC / name)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
