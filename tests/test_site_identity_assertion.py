from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from app.services.entitlements.site_bridge import SiteIdentityAssertionVerifier


def _assertion(secret: str, *, user: str, method: str, path: str, issued_at: int | None = None, nonce: str = "nonce_nonce_nonce_123") -> str:
    ts = int(time.time()) if issued_at is None else int(issued_at)
    payload = f"blackcrown:site-bridge:v1:{ts}:{nonce}:{method}:{path}:{user}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"v1.{ts}.{nonce}.{signature}"


def test_signed_site_identity_assertion_accepts_verified_pages_identity():
    secret = "s" * 48
    verifier = SiteIdentityAssertionVerifier(secret)
    token = _assertion(
        secret,
        user="site-user-123",
        method="POST",
        path="/integrations/site/telegram/link",
    )
    assert verifier.verify(
        assertion=token,
        site_user="site-user-123",
        method="POST",
        path="/integrations/site/telegram/link",
    ) == "site-user-123"


def test_signed_site_identity_assertion_is_bound_to_user_method_and_path():
    secret = "k" * 48
    verifier = SiteIdentityAssertionVerifier(secret)
    token = _assertion(
        secret,
        user="site-user-123",
        method="GET",
        path="/integrations/site/telegram/status",
    )
    with pytest.raises(PermissionError):
        verifier.verify(assertion=token, site_user="site-user-999", method="GET", path="/integrations/site/telegram/status")
    with pytest.raises(PermissionError):
        verifier.verify(assertion=token, site_user="site-user-123", method="POST", path="/integrations/site/telegram/status")
    with pytest.raises(PermissionError):
        verifier.verify(assertion=token, site_user="site-user-123", method="GET", path="/integrations/site/telegram/link")


def test_signed_site_identity_assertion_rejects_stale_or_unconfigured_tokens():
    secret = "z" * 48
    verifier = SiteIdentityAssertionVerifier(secret)
    stale = _assertion(
        secret,
        user="site-user-123",
        method="GET",
        path="/integrations/site/telegram/status",
        issued_at=int(time.time()) - 300,
    )
    with pytest.raises(PermissionError):
        verifier.verify(assertion=stale, site_user="site-user-123", method="GET", path="/integrations/site/telegram/status")
    assert SiteIdentityAssertionVerifier("short").configured is False
