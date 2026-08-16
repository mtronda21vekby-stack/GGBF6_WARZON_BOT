from __future__ import annotations

from types import SimpleNamespace

import app.webapp.quality_router as quality_router
from app.observability.quality import QualityTelemetry
from app.observability.readiness import readiness_snapshot
from app.services.storage.memory import InMemoryStore
from app.webapp.quality_router import FeedbackBody


def test_quality_telemetry_aggregates_without_content():
    telemetry = QualityTelemetry()
    telemetry.record_reply(
        intent="DEATH_ANALYSIS",
        latency_ms=420,
        knowledge="VERIFIED_STATIC",
        outcome="ok",
        attempts=2,
        anti_repeat_retry=True,
    )
    telemetry.record_feedback("helpful")
    snap = telemetry.snapshot()
    assert snap["requests"] == 1
    assert snap["avg_latency_ms"] == 420.0
    assert snap["retry_attempts"] == 1
    assert snap["anti_repeat_retries"] == 1
    assert snap["feedback"]["helpful_rate"] == 1.0
    assert "text" not in snap and "prompt" not in snap


def test_feedback_is_trusted_idempotent_and_stores_no_answer_text(monkeypatch):
    store = InMemoryStore()
    quality_router.bind_runtime(store=store)
    monkeypatch.setattr(quality_router, "verify_init_data", lambda _: (True, {"user_id": 77}))

    body = FeedbackBody(
        rating="not_helpful",
        response_hash="a" * 64,
        surface="miniapp_chat",
    )
    first = quality_router.submit_answer_feedback(body, x_telegram_init_data="signed")
    second = quality_router.submit_answer_feedback(body, x_telegram_init_data="signed")
    assert first == {"ok": True, "duplicate": False}
    assert second == {"ok": True, "duplicate": True}

    events = store.list_progression_events(77)
    feedback = [x for x in events if x.get("type") == "answer_feedback"]
    assert len(feedback) == 1
    assert feedback[0]["rating"] == "not_helpful"
    assert feedback[0]["response_hash"] == "a" * 64
    assert "answer" not in feedback[0] and "text" not in feedback[0]


def test_feedback_rejects_untrusted_context(monkeypatch):
    store = InMemoryStore()
    quality_router.bind_runtime(store=store)
    monkeypatch.setattr(quality_router, "verify_init_data", lambda _: (False, {}))
    body = FeedbackBody(rating="helpful", response_hash="b" * 64)
    try:
        quality_router.submit_answer_feedback(body, x_telegram_init_data="bad")
        raise AssertionError("expected HTTPException")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401


def test_readiness_never_exposes_secrets():
    settings = SimpleNamespace(
        ai_enabled=True,
        openai_api_key="OPENAI_SUPER_SECRET",
        supabase_service_role_key="SUPABASE_SUPER_SECRET",
        supabase_url="https://example.supabase.co",
        storage_backend="auto",
        live_knowledge_enabled=True,
        vod_enabled=True,
        voice_enabled=True,
    )
    snap = readiness_snapshot(settings, InMemoryStore())
    rendered = repr(snap)
    assert snap["features"]["ai"] is True
    assert snap["features"]["persistent_memory_configured"] is True
    assert "OPENAI_SUPER_SECRET" not in rendered
    assert "SUPABASE_SUPER_SECRET" not in rendered
    assert "example.supabase.co" not in rendered


def test_quality_routes_are_before_legacy_static_catchall():
    from app.webhook import create_app

    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths.index("/webapp/api/feedback") < paths.index("/webapp/{req_path:path}")
    assert "/health/details" in paths
