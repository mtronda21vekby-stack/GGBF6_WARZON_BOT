from pathlib import Path
import inspect

from app.services.crown_session import CrownSessionService
from app.ui.command_console import premium_view

ROOT = Path(__file__).resolve().parents[1]


def test_crown_session_public_entitlement_exposes_website_identity():
    class Status:
        linked = True
        premium = True
        entitlements = ("bco_premium",)
        site_user_id = "site-user-123"
        linked_at = "2026-08-19T12:00:00+00:00"

    data = CrownSessionService._public_entitlement(Status())
    assert data["site_user_id"] == "site-user-123"
    assert data["linked_at"]
    assert data["premium"] is True


def test_premium_view_keeps_link_flow_signature():
    params = inspect.signature(premium_view).parameters
    for name in ("error", "link_url", "link_ttl_minutes", "note", "profile"):
        assert name in params


def test_training_callbacks_match_controller_contract():
    source = (ROOT / "app" / "ui" / "command_console.py").read_text(encoding="utf-8")
    controller = (ROOT / "app" / "services" / "telegram" / "command_console.py").read_text(encoding="utf-8")
    assert "bco:set:focus:aim" in source
    assert 'field=="focus"' in controller or 'field == "focus"' in controller


def test_account_center_uses_server_ecosystem_projection():
    source = (ROOT / "app" / "webapp" / "static" / "bco.account-v55.js").read_text(encoding="utf-8")
    assert "session?.ecosystem" in source
    assert "ent.site_user_id" in source
    assert "https://blackcrown.work/account/telegram" in source
