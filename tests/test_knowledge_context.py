from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import (
    KnowledgeConfidence,
    KnowledgeRequest,
    StaticKnowledgeProvider,
)


def test_current_meta_is_not_faked_by_static_provider():
    provider = StaticKnowledgeProvider()
    req = KnowledgeRequest(
        intent=IntentResult(Intent.META_CURRENT, 0.99, needs_current_data=True),
        text="Какая сейчас мета?",
        profile={"game": "Warzone", "platform": "Xbox", "input": "Controller", "difficulty": "Pro"},
    )
    ctx = provider.query(req)
    assert ctx.confidence is KnowledgeConfidence.UNKNOWN
    assert ctx.is_verified_current is False


def test_catalog_settings_keep_provenance():
    provider = StaticKnowledgeProvider()
    req = KnowledgeRequest(
        intent=IntentResult(Intent.GAME_SETTINGS, 0.99),
        text="Настрой сенсу",
        profile={"game": "Warzone", "platform": "Xbox", "input": "Controller", "difficulty": "Pro"},
    )
    ctx = provider.query(req)
    assert ctx.confidence is KnowledgeConfidence.DATED_SOURCE
    assert ctx.source
    assert ctx.last_updated == "2025-12-11"
    assert ctx.facts
