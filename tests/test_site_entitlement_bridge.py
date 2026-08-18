from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from app.services.entitlements.service import EntitlementStatus
from app.services.entitlements.site_bridge import SiteEntitlementBridgeAPI, SiteSessionVerifier


SESSION_TOKEN = f"v1.{'p' * 24}.{'s' * 43}"


class FakeVerifier:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    async def verify(self, *, token: str, expected_user_id: str):
        self.calls.append((token, expected_user_id))
        if self.error:
            raise self.error
        return expected_user_id

    async def close(self):
        return None


class FakeEntitlements:
    def __init__(self):
        self.completed: list[tuple[str, str]] = []
        self.status_users: list[str] = []

    async def complete_site_link(self, *, code: str, site_user_id: str):
        self.completed.append((code, site_user_id))
        return EntitlementStatus(linked=True, premium=False, entitlements=(), linked_at="2026-08-16T00:00:00Z")

    async def get_site_status(self, site_user_id: str):
        self.status_users.append(site_user_id)
        return EntitlementStatus(
            linked=True,
            premium=True,
            entitlements=("bco_premium",),
            site_user_id=site_user_id,
            linked_at="2026-08-16T00:00:00Z",
        )


def run(coro):
    return asyncio.run(coro)


def make_app(verifier: FakeVerifier, entitlements: FakeEntitlements):
    app = FastAPI()
    bridge = SiteEntitlementBridgeAPI(
        settings=SimpleNamespace(),
        entitlements=entitlements,  # type: ignore[arg-type]
        verifier=verifier,  # type: ignore[arg-type]
    )
    app.include_router(bridge.router)
    return app


def request_headers(user_id: str = "site-user-a"):
    return {
        "x-bc-session-token": SESSION_TOKEN,
        "x-bc-site-user": user_id,
    }


def test_link_requires_independently_verified_site_identity():
    verifier = FakeVerifier()
    entitlements = FakeEntitlements()
    app = make_app(verifier, entitlements)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://bot.test") as client:
            response = await client.post(
                "/integrations/site/telegram/link",
                headers=request_headers("site-user-authoritative"),
                json={"code": "A" * 32, "siteUserId": "attacker-controlled"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "ok": True,
                "linked": True,
                "premium": False,
                "entitlements": [],
                "linkedAt": "2026-08-16T00:00:00Z",
            }

    run(scenario())
    assert verifier.calls == [(SESSION_TOKEN, "site-user-authoritative")]
    assert entitlements.completed == [("A" * 32, "site-user-authoritative")]


def test_session_mismatch_blocks_supabase_completion():
    verifier = FakeVerifier()
    verifier.error = PermissionError("site_session_mismatch")
    entitlements = FakeEntitlements()
    app = make_app(verifier, entitlements)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://bot.test") as client:
            response = await client.post(
                "/integrations/site/telegram/link",
                headers=request_headers(),
                json={"code": "A" * 32},
            )
            assert response.status_code == 401
            assert response.json()["reason"] == "site_session_mismatch"

    run(scenario())
    assert entitlements.completed == []


def test_status_response_does_not_expose_site_or_telegram_identity():
    verifier = FakeVerifier()
    entitlements = FakeEntitlements()
    app = make_app(verifier, entitlements)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://bot.test") as client:
            response = await client.get(
                "/integrations/site/telegram/status",
                headers=request_headers("site-user-b"),
            )
            payload = response.json()
            assert response.status_code == 200
            assert payload == {
                "ok": True,
                "linked": True,
                "premium": True,
                "entitlements": ["bco_premium"],
                "linkedAt": "2026-08-16T00:00:00Z",
            }
            assert "site_user_id" not in payload
            assert "telegram_user_id" not in payload

    run(scenario())


def test_site_session_verifier_uses_lightweight_crypto_endpoint_and_matches_id():
    observed = {}

    def handler(request: httpx.Request):
        observed["url"] = str(request.url)
        observed["cookie"] = request.headers.get("cookie")
        return httpx.Response(200, json={"ok": True, "userId": "site-user-c", "issuedAt": 1, "expiresAt": 2})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        verifier = SiteSessionVerifier(SimpleNamespace(), client=client)
        try:
            verified = await verifier.verify(token=SESSION_TOKEN, expected_user_id="site-user-c")
            assert verified == "site-user-c"
        finally:
            await client.aclose()

    run(scenario())
    assert observed == {
        "url": "https://blackcrown.work/api/auth/session/verify",
        "cookie": f"bc_session={SESSION_TOKEN}",
    }


def test_site_session_verifier_retains_explicit_legacy_api_me_compatibility():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"ok": True, "profile": {"id": "site-user-legacy"}})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        verifier = SiteSessionVerifier(
            SimpleNamespace(blackcrown_session_verify_url="https://blackcrown.work/api/me"),
            client=client,
        )
        try:
            assert await verifier.verify(token=SESSION_TOKEN, expected_user_id="site-user-legacy") == "site-user-legacy"
        finally:
            await client.aclose()

    run(scenario())


def test_site_session_verifier_rejects_unapproved_verify_path():
    try:
        SiteSessionVerifier(SimpleNamespace(blackcrown_session_verify_url="https://blackcrown.work/account/telegram"))
    except ValueError as exc:
        assert str(exc) == "blackcrown_verify_url_invalid"
    else:
        raise AssertionError("unapproved session verifier path must fail closed")
