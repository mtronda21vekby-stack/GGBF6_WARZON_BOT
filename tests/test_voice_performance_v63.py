from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_voice_turn_exposes_latency_breakdown():
    source = (ROOT / "app/webapp/voice_router.py").read_text(encoding="utf-8")
    assert '"stt_ms"' in source
    assert '"think_ms"' in source
    assert '"turn_ms"' in source
    assert '"X-BCO-TTS-MS"' in source


def test_fast_start_voice_layer_prefetches_remaining_reply():
    source = (ROOT / "app/webapp/static/bco.voice-v63.js").read_text(encoding="utf-8")
    assert "splitReply" in source
    assert "restPromise" in source
    assert "X-BCO-TTS-MS" in source
    assert "FAST START" in source


def test_v63_boots_after_v62_and_before_ru_layer():
    app = (ROOT / "app/webapp/static/app.js").read_text(encoding="utf-8")
    assert app.index("bco.voice-v62.js") < app.index("bco.voice-v63.js") < app.index("bco.ru-v55.js")


def test_voice_performance_does_not_move_into_webhook():
    webhook = (ROOT / "app/webhook.py").read_text(encoding="utf-8")
    assert "splitReply" not in webhook
    assert "X-BCO-TTS-MS" not in webhook
