from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "app" / "webapp" / "webapp_router_base.py").read_text(encoding="utf-8")
JS = (ROOT / "app" / "webapp" / "static" / "bco.chat-history-v60.js").read_text(encoding="utf-8")
APP = (ROOT / "app" / "webapp" / "static" / "app.js").read_text(encoding="utf-8")


def test_history_endpoint_is_trusted_and_server_owned():
    assert '/webapp/api/conversation-history' in BASE
    assert 'trusted_telegram_context_required' in BASE
    assert 'shared_server_conversation_store' in BASE
    assert 'history[-20:]' in BASE


def test_mini_app_hydrates_from_server_history():
    assert '/webapp/api/conversation-history' in JS
    assert 'X-Telegram-Init-Data' in JS
    assert 'СЕРВЕР' in JS
    assert '↻ История' in JS


def test_history_layer_boots_after_crown_chat_and_before_ru_layer():
    assert 'bco.chat-history-v60.js' in APP
    assert APP.index('bco.crown-chat-v59.js') < APP.index('bco.chat-history-v60.js')
    assert APP.index('bco.chat-history-v60.js') < APP.index('bco.ru-v55.js')
