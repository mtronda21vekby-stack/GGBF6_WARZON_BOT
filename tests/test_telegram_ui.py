from __future__ import annotations

import app.ui.quickbar as quickbar
from app.ui.entitlement_kb import kb_premium_bridge
from app.ui.presentation import LEGACY_DIVIDER, polish_telegram_text, tactical_card
from app.ui.quickbar import (
    kb_bf6_classes,
    kb_difficulty,
    kb_game_settings_menu,
    kb_games,
    kb_input,
    kb_main,
    kb_platform,
    kb_premium,
    kb_roles,
    kb_settings,
    kb_voice,
    kb_zombies_home,
    kb_zombies_maps,
    kb_zombies_sections,
)


def _rows(markup: dict) -> list[list[dict]]:
    return list(markup.get("inline_keyboard") or markup.get("keyboard") or [])


def _labels(markup: dict) -> list[str]:
    return [str(button.get("text") or "") for row in _rows(markup) for button in row]


def _reply_keyboards() -> list[dict]:
    return [
        kb_premium(),
        kb_premium_bridge(),
        kb_voice(),
        kb_settings(),
        kb_games(),
        kb_platform(),
        kb_input(),
        kb_difficulty(),
        kb_roles(),
        kb_bf6_classes(),
        kb_game_settings_menu("Warzone"),
        kb_game_settings_menu("BO7"),
        kb_game_settings_menu("BF6"),
        kb_zombies_home(),
        kb_zombies_maps(),
        kb_zombies_sections(),
    ]


def test_main_response_bar_is_inline_and_does_not_recreate_bottom_keyboard(monkeypatch):
    monkeypatch.delenv("WEBAPP_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    quickbar._BUILD_CACHE_VALUE = None

    markup = kb_main()
    labels = _labels(markup)

    assert "keyboard" not in markup
    assert len(markup["inline_keyboard"]) == 1
    assert labels == ["◼ COMMAND CONSOLE"]
    button = markup["inline_keyboard"][0][0]
    assert button["callback_data"] == "bco:home"
    assert button["style"] == "primary"
    assert "🧹 Очистить память" not in labels
    assert "🧨 Сброс" not in labels


def test_settings_deck_preserves_role_and_guarded_system_actions():
    labels = _labels(kb_settings())
    assert "🎭 Роль/Класс" in labels
    assert "🎙 Голос: Тиммейт/Коуч" in labels
    assert "🧹 Очистить память" in labels
    assert "🧨 Сброс" in labels
    assert labels[-1] == "⬅️ Назад"


def test_configured_miniapp_is_branded_as_command_center(monkeypatch):
    monkeypatch.setenv("WEBAPP_URL", "https://example.test/webapp")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("WEBAPP_BUILD_ID", "ui-v16")
    quickbar._BUILD_CACHE_VALUE = None

    markup = kb_main()
    buttons = [button for row in _rows(markup) for button in row]
    command_center = next(button for button in buttons if button["text"] == "🛰 COMMAND CENTER")
    assert command_center["web_app"]["url"] == "https://example.test/webapp?v=ui-v16"


def test_legacy_submenus_respect_telegram_button_and_placeholder_limits(monkeypatch):
    monkeypatch.delenv("WEBAPP_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    quickbar._BUILD_CACHE_VALUE = None

    for keyboard in _reply_keyboards():
        assert keyboard["resize_keyboard"] is True
        assert keyboard["is_persistent"] is True
        assert len(keyboard["input_field_placeholder"]) <= 64
        for row in keyboard["keyboard"]:
            assert 1 <= len(row) <= 2
            for button in row:
                assert 1 <= len(button["text"]) <= 64


def test_legacy_ai_frame_becomes_compact_tactical_card():
    legacy = (
        "🖤 BLACK CROWN OPS · 🤝 ТИММЕЙТ\n"
        f"{LEGACY_DIVIDER}\n\n"
        "Держи высоту и не отдавай сильную позицию.\n\n"
        f"{LEGACY_DIVIDER}\n"
        "— BCO 😈"
    )
    polished = polish_telegram_text(legacy)

    assert polished.startswith("◼ BLACK CROWN OPS // TEAMMATE\n")
    assert "Держи высоту" in polished
    assert LEGACY_DIVIDER not in polished
    assert "— BCO" not in polished


def test_start_manifest_is_replaced_with_fast_onboarding_card():
    legacy = (
        "👑 BLACK CROWN OPS · 📚 КОУЧ\n"
        f"{LEGACY_DIVIDER}\n\n"
        "BLACK CROWN OPS — это искусственный разум для соревновательных FPS.\n"
        "Очень длинный старый манифест.\n\n"
        f"{LEGACY_DIVIDER}\n"
        "— BCO 😈"
    )
    polished = polish_telegram_text(legacy)

    assert polished.startswith("◼ BLACK CROWN OPS // COACH")
    assert "AI-оператор для Warzone · BO7 · BF6 · Zombies." in polished
    assert "Почему я умер на ротации?" in polished
    assert "Очень длинный старый манифест" not in polished


def test_premium_panel_uses_same_visual_language():
    polished = polish_telegram_text(
        "💎 BLACK CROWN PREMIUM\n\nСвязка с сайтом: АКТИВНА\nPremium: ACTIVE ✅"
    )
    assert polished == tactical_card(
        "Связка с сайтом: АКТИВНА\nPremium: ACTIVE ✅",
        channel="PREMIUM",
    )
