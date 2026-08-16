from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.services.entitlements.service import PremiumEntitlementService


TOKEN = "A" * 32


def settings(**overrides):
    base = {
        "premium_link_enabled": True,
        "supabase_url": "https://wqriwhciqvrbhkkiuhxb.supabase.co",
        "supabase_service_role_key": "sb_secret_test_server_key",
        "blackcrown_account_url": "https://blackcrown.work/account/telegram",
        "premium_link_ttl_s": 600,
        "entitlement_timeout_s": 3.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def run(coro):
    return asyncio.run(coro)


def test_create_link_hashes_token_and_uses_secret_key_without_bearer():
    observed = {}

    def handler(request: httpx.Request):
        observed["headers"] = dict(request.headers)
        observed["json"] = __import__("json").loads(request.content.decode("utf-8"))
        assert request.url.path.endswith("/rpc/blackcrown_create_telegram_link_challenge")
        return httpx.Response(200, json={"ok": True, "ttl_seconds": 600, "expires_at": "2026-08-16T20:00:00Z"})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = PremiumEntitlementService(settings(), client=client)
        try:
            with patch("app.services.entitlements.service.secrets.token_urlsafe", return_value=TOKEN):
                challenge = await service.create_link_challenge(
                    telegram_user_id=8275036156,
                    telegram_chat_id=8275036156,
                    telegram_username="GGBF6_TEST!",
                )
            assert challenge.code == TOKEN
            assert challenge.url == f"https://blackcrown.work/account/telegram#telegram-link={TOKEN}"
            assert challenge.ttl_seconds == 600
        finally:
            await client.aclose()

    run(scenario())
    assert observed["json"]["p_code_hash"] == hashlib.sha256(TOKEN.encode()).hexdigest()
    assert observed["json"]["p_telegram_username"] == "GGBF6_TEST"
    assert observed["headers"]["apikey"] == "sb_secret_test_server_key"
    assert "authorization" not in observed["headers"]


def test_legacy_service_role_jwt_keeps_bearer_compatibility():
    observed = {}

    def handler(request: httpx.Request):
        observed.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True, "linked": False, "premium": False, "entitlements": []})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = PremiumEntitlementService(
            settings(supabase_service_role_key="legacy.service.role.jwt"),
            client=client,
        )
        try:
            await service.get_status(123)
        finally:
            await client.aclose()

    run(scenario())
    assert observed["authorization"] == "Bearer legacy.service.role.jwt"


def test_publishable_key_is_rejected_for_server_entitlement_calls():
    service = PremiumEntitlementService(
        settings(supabase_service_role_key="sb_publishable_not_server"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
    )
    assert service.configured is False
    with pytest.raises(RuntimeError, match="premium_link_not_configured"):
        run(service.get_status(123))
    run(service._client.aclose())  # test-owned client


def test_status_requires_authoritative_bco_premium_entitlement():
    responses = [
        {"ok": True, "linked": True, "premium": True, "entitlements": ["cosmetic_gold"]},
        {"ok": True, "linked": True, "premium": True, "entitlements": ["bco_premium", "bco_premium"]},
    ]

    def handler(_request: httpx.Request):
        return httpx.Response(200, json=responses.pop(0))

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = PremiumEntitlementService(settings(), client=client)
        try:
            first = await service.get_status(123)
            second = await service.get_status(123)
            assert first.linked is True
            assert first.premium is False
            assert second.premium is True
            assert second.entitlements == ("bco_premium",)
        finally:
            await client.aclose()

    run(scenario())


def test_unlink_uses_server_only_rpc():
    def handler(request: httpx.Request):
        assert request.url.path.endswith("/rpc/blackcrown_unlink_telegram")
        assert __import__("json").loads(request.content.decode("utf-8")) == {"p_telegram_user_id": 123}
        return httpx.Response(200, json={"ok": True, "unlinked": True})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = PremiumEntitlementService(settings(), client=client)
        try:
            assert await service.unlink(123) is True
        finally:
            await client.aclose()

    run(scenario())
