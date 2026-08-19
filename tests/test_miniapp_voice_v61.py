from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_voice_router_is_isolated_from_base_router():
    source = (ROOT / "app/webapp/webapp_router.py").read_text(encoding="utf-8")
    assert "from app.webapp import voice_router as _voice" in source
    assert "router.include_router(_voice.router)" in source
    assert "_base.bind_runtime(" in source
    assert "_voice.bind_runtime(" in source


def test_voice_endpoints_require_trusted_telegram_context():
    source = (ROOT / "app/webapp/voice_router.py").read_text(encoding="utf-8")
    assert 'trusted_telegram_context_required' in source
    assert '@router.post("/webapp/api/voice-turn")' in source
    assert '@router.post("/webapp/api/voice-speak")' in source
    assert "APP_TRANSCRIPTION.transcribe_result" in source
    assert "APP_BRAIN" in source
    assert "APP_VOICE.synthesize" in source


def test_webhook_only_binds_existing_voice_runtime_to_webapp():
    source = (ROOT / "app/webhook.py").read_text(encoding="utf-8")
    assert "transcription=transcription_backend" in source
    assert "voice=voice_service" in source
    assert "voice_ingress.transform(upd)" in source
    assert "voice_controller.maybe_auto" in source


def test_multipart_runtime_dependency_is_pinned():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "python-multipart==" in requirements


def test_voice_ui_uses_media_recorder_and_shared_history():
    source = (ROOT / "app/webapp/static/bco.voice-v61.js").read_text(encoding="utf-8")
    assert "MediaRecorder" in source
    assert "/webapp/api/voice-turn" in source
    assert "/webapp/api/voice-speak" in source
    assert "BCO_CHAT_HISTORY" in source
    assert "TELEGRAM FALLBACK" in source
