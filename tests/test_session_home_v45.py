from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_session_home_boots_after_crown_session_before_operator():
    text = (ROOT / "app/webapp/static/app.js").read_text(encoding="utf-8")
    crown = text.index("/webapp/bco.crown-session.js")
    home = text.index("/webapp/bco.session-home.js")
    operator = text.index("/webapp/bco.operator.js")
    assert crown < home < operator


def test_session_home_is_crown_session_driven_and_keeps_legacy_home():
    text = (ROOT / "app/webapp/static/bco.session-home.js").read_text(encoding="utf-8")
    assert '$("#tab-home")' in text
    assert "home.prepend(section)" in text
    assert "window.BCO_CROWN_SESSION?.refresh?.(false)" in text
    assert 'window.addEventListener("bco:crown-session"' in text
    assert "PREPARE SESSION" in text
    assert "window.BCO_OPERATOR?.refresh?.(true)" in text
    assert "identity.black_crown_user_id" in text
    assert "entitlement.premium" in text
    assert "session.personal_meta" in text


def test_session_home_has_unique_coverage_targets():
    text = (ROOT / "app/webapp/static/bco.session-home.js").read_text(encoding="utf-8")
    assert text.count('id="bcoShCoverage"') == 1
    assert text.count('id="bcoShKnown"') == 1
