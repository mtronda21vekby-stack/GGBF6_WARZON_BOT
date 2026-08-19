from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_boot_loads_crown_session_before_operator_and_war_room():
    app = read("app/webapp/static/app.js")
    session_idx = app.index("/webapp/bco.crown-session.js")
    operator_idx = app.index("/webapp/bco.operator.js")
    war_room_idx = app.index("/webapp/bco.war-room.js")
    assert session_idx < operator_idx < war_room_idx


def test_crown_session_client_uses_trusted_telegram_init_data():
    js = read("app/webapp/static/bco.crown-session.js")
    assert '"/webapp/api/crown-session"' in js
    assert "X-Telegram-Init-Data" in js
    assert "window.Telegram?.WebApp?.initData" in js
    assert "BCO_CROWN_SESSION" in js


def test_war_room_prefers_unified_crown_session_contract():
    js = read("app/webapp/static/bco.war-room.js")
    assert "BCO_CROWN_SESSION?.getSnapshot" in js
    assert "operator_twin" in js
    assert "personal_meta" in js
    assert "black_crown_user_id" in js
    assert "entitlement" in js
    assert "CROWN SESSION" in js


def test_server_exposes_trusted_crown_session_endpoint():
    router = read("app/webapp/command_center_router.py")
    assert '@router.get("/webapp/api/crown-session")' in router
    assert "CrownSessionService" in router
    assert "_trusted_meta" in router
