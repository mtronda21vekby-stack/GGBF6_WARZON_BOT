from pathlib import Path

from app.services.ecosystem_catalog import MODULES, ecosystem_modules
from app.ui.command_console import home_view


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "webapp" / "static"


def _callbacks(markup):
    out = set()
    for row in (markup or {}).get("inline_keyboard", []):
        for button in row:
            data = str(button.get("callback_data") or "")
            if data:
                out.add(data)
    return out


def test_ecosystem_catalog_matches_telegram_command_console_home():
    callbacks = _callbacks(home_view({}).reply_markup)
    expected = {m.bot_callback for m in MODULES if m.bot_callback}
    assert expected <= callbacks
    assert {m.id for m in MODULES} == {
        "ai_brief", "training", "world", "vod", "zombies", "operator", "premium", "system"
    }
    assert len(ecosystem_modules()) == 8


def test_mini_app_ecosystem_shell_exposes_clear_five_zone_navigation():
    source = (STATIC / "bco.ecosystem-shell.js").read_text(encoding="utf-8")
    for label in ("HOME", "CROWN", "VOD", "OPERATOR", "MORE"):
        assert label in source
    for module in ("AI Combat Brief", "TRAINING", "WORLD", "VOD LAB", "ZOMBIES", "OPERATOR", "PREMIUM", "SYSTEM"):
        assert module.upper() in source.upper()
    assert "ONE BLACK CROWN ACCOUNT" in source
    assert "BCO_CROWN_SESSION" in source


def test_server_profile_projection_is_loaded_before_ecosystem_shell():
    boot = (STATIC / "app.js").read_text(encoding="utf-8")
    projection = "bco.profile-projection.js"
    shell = "bco.ecosystem-shell.js"
    assert projection in boot
    assert shell in boot
    assert boot.index(projection) < boot.index(shell)

    source = (STATIC / "bco.profile-projection.js").read_text(encoding="utf-8")
    for root in ("segGame", "segPlatform", "segInput", "segMode", "segVoice", "segFocus"):
        assert root in source
    assert "bco:crown-session" in source
