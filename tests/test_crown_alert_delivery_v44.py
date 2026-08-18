from types import SimpleNamespace

from app.services.brain.crown_alert_delivery import alert_key, decide_delivery


def change(**patch):
    base = {"game":"warzone","from_hash":"old","to_hash":"new"}
    base.update(patch)
    return base


def test_baseline_can_never_alert():
    result = decide_delivery(change(from_hash=""), SimpleNamespace(relevant=True, score=9))
    assert result.deliver is False
    assert result.reason == "baseline_not_alert"


def test_duplicate_is_suppressed():
    result = decide_delivery(change(), SimpleNamespace(relevant=True, score=9), already_seen=True)
    assert result.deliver is False
    assert result.reason == "duplicate_suppressed"


def test_personal_relevance_controls_priority():
    standard = decide_delivery(change(), SimpleNamespace(relevant=True, score=3))
    high = decide_delivery(change(), SimpleNamespace(relevant=True, score=7))
    quiet = decide_delivery(change(), SimpleNamespace(relevant=False, score=9))
    assert standard.deliver is True and standard.priority == "STANDARD"
    assert high.deliver is True and high.priority == "HIGH"
    assert quiet.deliver is False


def test_alert_key_is_deterministic_and_identity_independent():
    assert alert_key(change()) == alert_key(change())
    assert len(alert_key(change())) == 24
