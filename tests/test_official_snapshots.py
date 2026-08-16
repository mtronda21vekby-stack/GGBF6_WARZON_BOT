from datetime import datetime, timezone
import json

from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeConfidence, KnowledgeRequest
from app.services.knowledge.official_snapshots import OfficialSnapshotProvider


def _intent(intent: Intent) -> IntentResult:
    return IntentResult(
        intent=intent,
        confidence=1.0,
        needs_current_data=intent in {Intent.META_CURRENT, Intent.PATCH_CURRENT},
        needs_player_memory=False,
        preferred_depth="medium",
    )


def _request(intent: Intent, text: str, game: str = "Warzone") -> KnowledgeRequest:
    return KnowledgeRequest(intent=_intent(intent), text=text, profile={"game": game})


def test_fresh_official_warzone_snapshot_is_verified_current():
    provider = OfficialSnapshotProvider(
        max_age_hours=168,
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.PATCH_CURRENT, "что изменили в последнем патче Warzone?"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert "callofduty.com" in ctx.source
    assert any("AK-27" in fact.text for fact in ctx.facts)


def test_snapshot_expires_and_loses_current_status():
    provider = OfficialSnapshotProvider(
        max_age_hours=168,
        now_fn=lambda: datetime(2026, 8, 24, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.META_CURRENT, "что сейчас мета в Warzone?"))
    assert ctx.confidence == KnowledgeConfidence.DATED_SOURCE
    assert not ctx.is_verified_current


def test_text_game_override_selects_bo7_even_when_profile_is_warzone():
    provider = OfficialSnapshotProvider(
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.PATCH_CURRENT, "последний патч BO7", game="Warzone"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert "Treyarch" in ctx.source
    assert any("AN-94" in fact.text for fact in ctx.facts)


def test_bf6_snapshot_is_available_for_current_patch_questions():
    provider = OfficialSnapshotProvider(
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.PATCH_CURRENT, "что сейчас по патчу Battlefield 6?", game="BF6"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert any("1.4.1.0" in fact.text for fact in ctx.facts)


def test_meta_context_explicitly_forbids_turning_patch_notes_into_official_ranking():
    provider = OfficialSnapshotProvider(
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.META_CURRENT, "какая сейчас мета Warzone?"))
    assert ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT
    assert any("not a definitive weapon meta ranking" in fact.text for fact in ctx.facts)


def test_unapproved_domain_never_gets_verified_current(tmp_path):
    payload = {
        "schema_version": 1,
        "game": "warzone",
        "title": "Fake current data",
        "publisher": "Unknown",
        "source_kind": "official_patch_notes",
        "source_url": "https://example.com/not-official",
        "published_at": "2026-08-16T00:00:00Z",
        "verified_at": "2026-08-16T08:00:00Z",
        "facts": [{"text": "fake", "tags": ["weapon_balance"]}],
    }
    (tmp_path / "warzone.json").write_text(json.dumps(payload), encoding="utf-8")
    provider = OfficialSnapshotProvider(
        base_dir=tmp_path,
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.META_CURRENT, "meta Warzone"))
    assert ctx.confidence == KnowledgeConfidence.DATED_SOURCE
    assert not ctx.is_verified_current


def test_provider_is_silent_for_non_current_intents():
    provider = OfficialSnapshotProvider(
        now_fn=lambda: datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
    )
    ctx = provider.query(_request(Intent.DEATH_ANALYSIS, "почему умер на ротации?"))
    assert ctx.confidence == KnowledgeConfidence.UNKNOWN
    assert ctx.facts == []
