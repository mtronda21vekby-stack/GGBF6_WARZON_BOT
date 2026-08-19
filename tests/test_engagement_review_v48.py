from pathlib import Path


def test_after_action_ui_renders_only_server_engagement_payload():
    text = Path("app/webapp/static/bco.after-action.js").read_text(encoding="utf-8")
    assert "data?.engagements" in text
    assert "slice(0, 6)" in text
    assert "SAMPLED FRAME ONLY" in text
    assert "FIRST DAMAGE" in text
    assert "MISSION RELEVANT" in text
    assert "INSUFFICIENT EVIDENCE" in text
    assert "window.__BCO_AFTER_ACTION_V48_LOADED__" in text


def test_boot_uses_after_action_v48_marker():
    text = Path("app/webapp/static/app.js").read_text(encoding="utf-8")
    assert "__BCO_AFTER_ACTION_V48_LOADED__" in text
    assert "bco.after-action.js" in text


def test_engagement_review_does_not_claim_continuous_video_truth():
    text = Path("app/webapp/static/bco.after-action.js").read_text(encoding="utf-8")
    assert "no continuous sequence claim" in text
    assert "first_damage == null" in text
