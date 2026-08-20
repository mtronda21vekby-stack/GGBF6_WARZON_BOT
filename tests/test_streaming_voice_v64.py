from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_ROUTER = ROOT / "app" / "webapp" / "voice_router.py"
STATIC = ROOT / "app" / "webapp" / "static"


def test_stt_only_endpoint_does_not_call_brain_reply():
    src = VOICE_ROUTER.read_text(encoding="utf-8")
    start = src.index('@router.post("/webapp/api/voice-transcribe")')
    end = src.index('@router.post("/webapp/api/voice-turn")')
    block = src[start:end]
    assert "_transcribe_upload" in block
    assert "_reply(" not in block
    assert '"authority": "stt_only_shared_voice_runtime"' in block


def test_v64_streams_only_completed_phrases_and_respects_reset():
    src = (STATIC / "bco.voice-v64.js").read_text(encoding="utf-8")
    assert "/webapp/api/voice-transcribe" in src
    assert "/webapp/api/ask/stream" in src
    assert "/webapp/api/voice-speak" in src
    assert "completedFrom" in src
    assert "streamReset=true" in src
    assert 'if(streamReset)return' in src
    assert 'event?.type === "final"' not in src  # minified implementation uses e.type
    assert 'e.type==="final"' in src


def test_v64_boots_after_v63_before_ru_layer():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert app.index("bco.voice-v63.js") < app.index("bco.voice-v64.js") < app.index("bco.ru-v55.js")
