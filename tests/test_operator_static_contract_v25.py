from pathlib import Path


def test_operator_surface_is_evidence_first_and_server_authoritative():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/webapp/static/bco.operator.js").read_text(encoding="utf-8")
    css = (root / "app/webapp/static/bco.operator.css").read_text(encoding="utf-8")
    app_js = (root / "app/webapp/static/app.js").read_text(encoding="utf-8")
    assert "/webapp/api/operator-intelligence" in js
    assert "/webapp/api/operator-mission/accept" in js
    assert "/webapp/api/operator-mission/complete" in js
    assert "No hidden score" in js
    assert "Unknown remains unknown" in js
    assert "X-Telegram-Init-Data" in js
    assert "gold" not in css.casefold()
    assert "bco.operator.js" in app_js
