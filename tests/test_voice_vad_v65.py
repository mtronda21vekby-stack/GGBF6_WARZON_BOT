from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "webapp" / "static"


def test_v65_boots_after_streaming_voice():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "bco.voice-v64.js" in app
    assert "bco.voice-v65.js" in app
    assert app.index("bco.voice-v64.js") < app.index("bco.voice-v65.js")


def test_v65_has_adaptive_vad_and_manual_stop():
    src = (STATIC / "bco.voice-v65.js").read_text(encoding="utf-8")
    assert "const SILENCE=900" in src
    assert "const SILENCE=900,MIN_SPEECH=320,CAL=700,MAX=30000" in src
    assert "heard&&lastVoice&&now-lastVoice>SILENCE" in src
    assert "if(!heard)" in src
    assert "function finish()" in src


def test_v65_reuses_streaming_voice_endpoints_only():
    src = (STATIC / "bco.voice-v65.js").read_text(encoding="utf-8")
    assert "/webapp/api/voice-transcribe" in src
    assert "/webapp/api/ask/stream" in src
    assert "/webapp/api/voice-speak" in src
    assert "/tg/webhook" not in src
