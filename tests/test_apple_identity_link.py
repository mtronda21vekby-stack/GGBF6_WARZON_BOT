from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from app.services.identity.apple_link import (
    AppleIdentityLinkRejected,
    AppleIdentityLinkService,
)


APPLE_SUBJECT = "33333333-3333-4333-8333-333333333333"
LINK_ID = "44444444-4444-4444-8444-444444444444"
CODE = "A" * 32


def settings(**overrides):
    values = {
        "supabase_url": "https://wqriwhciqvrbhkkiuhxb.supabase.co",
        "supabase_service_role_key": "sb_secret_test_server_key",
        "telegram_bot_username": "GGBF6_WARZON_BOT",
        "apple_account_link_ttl_s": 600,
        "apple_account_link_timeout_s": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def run(coro):
    return asyncio.run(coro)


def test_link_start_hashes_single_use_code_and_never_sends_canonical_owner():
    observed = {}

    def handler(request: httpx.Request):
        observed["body"] = json.loads(request.content)
        observed["headers"] = dict(request.headers)
        assert request.url.path.endswith("/rpc/black_crown_start_apple_telegram_link")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "status": "pending",
                "link_id": LINK_ID,
                "expires_at": "2026-08-25T16:00:00Z",
                "ttl_seconds": 600,
            },
        )

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = AppleIdentityLinkService(settings(), client=client)
        try:
            with patch("app.services.identity.apple_link.secrets.token_urlsafe", return_value=CODE):
                challenge = await service.start(APPLE_SUBJECT)
            assert challenge.link_id == UUID(LINK_ID)
            assert challenge.verification_url.endswith(f"?start=crownlink_{CODE}")
        finally:
            await client.aclose()

    run(scenario())
    assert observed["body"] == {
        "p_apple_subject": APPLE_SUBJECT,
        "p_code_hash": hashlib.sha256(CODE.encode()).hexdigest(),
        "p_ttl_seconds": 600,
    }
    assert "black_crown_user_id" not in observed["body"]
    assert "p_code" not in observed["body"]
    assert "authorization" not in observed["headers"]


def test_link_status_is_bound_to_authenticated_apple_subject():
    observed = {}

    def handler(request: httpx.Request):
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"ok": True, "status": "pending", "expires_at": "2026-08-25T16:00:00Z"},
        )

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = AppleIdentityLinkService(settings(), client=client)
        try:
            result = await service.status(link_id=UUID(LINK_ID), apple_subject=APPLE_SUBJECT)
            assert result.status == "pending"
        finally:
            await client.aclose()

    run(scenario())
    assert observed == {"p_link_id": LINK_ID, "p_apple_subject": APPLE_SUBJECT}


def test_telegram_completion_uses_server_observed_sender_and_is_replay_aware():
    observed = {}

    def handler(request: httpx.Request):
        observed.update(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "status": "linked", "replayed": True})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = AppleIdentityLinkService(settings(), client=client)
        try:
            result = await service.complete_from_telegram(code=CODE, telegram_user_id=123456)
            assert result.status == "linked"
            assert result.replayed is True
        finally:
            await client.aclose()

    run(scenario())
    assert observed == {"p_code": CODE, "p_telegram_user_id": 123456}


def test_conflict_and_expiry_are_typed_and_publishable_keys_fail_closed():
    responses = [
        {"ok": False, "reason": "apple_identity_conflict"},
        {"ok": False, "reason": "link_expired"},
    ]

    def handler(_request: httpx.Request):
        return httpx.Response(200, json=responses.pop(0))

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        service = AppleIdentityLinkService(settings(), client=client)
        try:
            with pytest.raises(AppleIdentityLinkRejected, match="apple_identity_conflict"):
                await service.complete_from_telegram(code=CODE, telegram_user_id=123)
            with pytest.raises(AppleIdentityLinkRejected, match="link_expired"):
                await service.complete_from_telegram(code=CODE, telegram_user_id=123)
        finally:
            await client.aclose()

    run(scenario())
    rejected = AppleIdentityLinkService(
        settings(supabase_service_role_key="sb_publishable_not_server"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    )
    assert rejected.configured is False
    run(rejected._client.aclose())


def test_migration_enforces_atomic_verified_link_without_email_merge():
    sql = (Path(__file__).parents[1] / "migrations/012_verified_apple_identity_link.sql").read_text()
    assert "for update" in sql.lower()
    assert "provider = 'telegram'" in sql
    assert "provider = 'website_auth'" in sql
    assert "provider = 'apple'" in sql
    assert "apple_identity_linked" in sql
    assert "status = 'linked'" in sql
    assert "revoke all on table" in sql.lower()
    assert "to service_role" in sql.lower()
    assert "email" not in sql.lower()
    assert "p_black_crown_user_id" not in sql
