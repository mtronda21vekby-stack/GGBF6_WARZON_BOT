from __future__ import annotations

import asyncio
import json

import httpx

from app.adapters.telegram.client import TelegramClient
from app.ui.entitlement_kb import kb_premium_unlink_confirm
from app.ui.native_buttons import (
    VALID_BUTTON_STYLES,
    clear_native_button_cache,
    decorate_reply_markup,
    strip_advanced_button_fields,
)
from app.ui.presentation import tactical_card
from app.ui.quickbar import kb_main, kb_settings
from app.ui.rich_messages import tactical_rich_message
from app.ui.voice_kb import kb_voice_panel
from app.ui.zombies_kb import kb_zombies_hub


def _buttons(markup: dict) -> list[dict]:
    field = "keyboard" if "keyboard" in markup else "inline_keyboard"
    return [button for row in markup.get(field) or [] for button in row]


def _by_text(markup: dict) -> dict[str, dict]:
    return {str(button.get("text") or ""): button for button in _buttons(markup)}


def test_main_command_deck_uses_native_color_semantics():
    buttons = _by_text(kb_main())

    assert buttons["🧠 ИИ"]["style"] == "primary"
    assert buttons["🎯 Тренировка"]["style"] == "success"
    assert buttons["🧟 Zombies"]["style"] == "danger"
    assert buttons["💎 Premium"]["style"] == "success"
    command_center = buttons.get("🛰 COMMAND CENTER") or buttons.get("🛰 MINI APP")
    assert command_center is not None
    assert command_center["style"] == "primary"
    assert "style" not in buttons["⚙️ Настройки"]

    for button in buttons.values():
        if "style" in button:
            assert button["style"] in VALID_BUTTON_STYLES


def test_destructive_actions_are_red_and_navigation_is_neutral():
    settings = _by_text(kb_settings())
    confirmation = _by_text(kb_premium_unlink_confirm())

    assert settings["🧹 Очистить память"]["style"] == "danger"
    assert settings["🧨 Сброс"]["style"] == "danger"
    assert confirmation["⚠️ Подтвердить отвязку"]["style"] == "danger"
    assert "style" not in confirmation["Отмена"]


def test_legacy_keyboard_modules_are_styled_at_transport_boundary():
    voice = _by_text(decorate_reply_markup(kb_voice_panel()) or {})
    zombies = _by_text(decorate_reply_markup(kb_zombies_hub()) or {})

    assert voice["🔇 Voice OFF"]["style"] == "danger"
    assert voice["🔊 Voice AUTO"]["style"] == "success"
    assert voice["📚 Коуч"]["style"] == "primary"
    assert zombies["🗺 Карты"]["style"] == "primary"
    assert zombies["🧪 Перки"]["style"] == "success"


def test_optional_custom_emoji_ids_are_exact_label_scoped(monkeypatch):
    monkeypatch.setenv(
        "TELEGRAM_BUTTON_CUSTOM_EMOJI_JSON",
        json.dumps({"🧠 ИИ": "5368324170671202286", "bad": "not-an-id"}),
    )
    clear_native_button_cache()
    try:
        markup = decorate_reply_markup({"keyboard": [[{"text": "🧠 ИИ"}, {"text": "bad"}]]}) or {}
        buttons = _by_text(markup)
        assert buttons["🧠 ИИ"]["icon_custom_emoji_id"] == "5368324170671202286"
        assert "icon_custom_emoji_id" not in buttons["bad"]
    finally:
        clear_native_button_cache()


def test_advanced_button_fields_can_be_removed_for_legacy_api_fallback():
    styled = decorate_reply_markup({"keyboard": [[{"text": "🧠 ИИ"}]]}) or {}
    clean = strip_advanced_button_fields(styled) or {}

    assert _by_text(styled)["🧠 ИИ"]["style"] == "primary"
    assert "style" not in _by_text(clean)["🧠 ИИ"]


def test_tactical_rich_message_escapes_untrusted_text():
    rich = tactical_rich_message(tactical_card("Пикни <enemy> & не отдавай угол.", channel="TEAMMATE"))

    assert rich is not None
    assert "<h3>BLACK CROWN OPS // TEAMMATE</h3>" in rich["html"]
    assert "&lt;enemy&gt; &amp;" in rich["html"]
    assert "<enemy>" not in rich["html"]
    assert rich["skip_entity_detection"] is True


def test_client_prefers_rich_message_and_preserves_native_styles():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append({
            "path": request.url.path,
            "payload": json.loads(request.content.decode("utf-8")),
        })
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async def scenario() -> None:
        client = TelegramClient("TEST")
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await client.send_message(
                123,
                tactical_card("Контакт <left>.\n\n• держи высоту\n• дай инфу", channel="TEAMMATE"),
                {"keyboard": [[{"text": "🧠 ИИ"}, {"text": "🎯 Тренировка"}]]},
            )
        finally:
            await client.close()

    asyncio.run(scenario())

    assert [item["path"] for item in requests] == ["/botTEST/sendRichMessage"]
    payload = requests[0]["payload"]
    assert payload["reply_markup"]["keyboard"][0][0]["style"] == "primary"
    assert payload["reply_markup"]["keyboard"][0][1]["style"] == "success"
    assert "&lt;left&gt;" in payload["rich_message"]["html"]


def test_client_falls_back_to_plain_text_and_legacy_buttons():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append({"path": request.url.path, "payload": payload})
        if request.url.path.endswith("/sendRichMessage"):
            return httpx.Response(404, json={"ok": False, "description": "method not found"})
        button = payload.get("reply_markup", {}).get("keyboard", [[{}]])[0][0]
        if "style" in button:
            return httpx.Response(400, json={"ok": False, "description": "unknown field style"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    async def scenario() -> None:
        client = TelegramClient("TEST")
        await client._client.aclose()
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await client.send_message(
                123,
                tactical_card("Fallback path", channel="SYSTEM"),
                {"keyboard": [[{"text": "🧠 ИИ"}]]},
            )
        finally:
            await client.close()

    asyncio.run(scenario())

    assert [item["path"] for item in requests] == [
        "/botTEST/sendRichMessage",
        "/botTEST/sendMessage",
        "/botTEST/sendMessage",
    ]
    assert requests[1]["payload"]["reply_markup"]["keyboard"][0][0]["style"] == "primary"
    assert "style" not in requests[2]["payload"]["reply_markup"]["keyboard"][0][0]
