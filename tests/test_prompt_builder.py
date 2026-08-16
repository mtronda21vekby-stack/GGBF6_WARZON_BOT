from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeConfidence, KnowledgeContext, KnowledgeFact
from app.services.brain.prompt_builder import PromptBuilder
from app.services.brain.response_policy import get_response_policy


def _build(intent: Intent, voice="TEAMMATE", difficulty="Normal", knowledge=None):
    ir = IntentResult(intent, 0.99, needs_current_data=intent in {Intent.META_CURRENT, Intent.PATCH_CURRENT})
    profile = {"game": "Warzone", "platform": "Xbox", "input": "Controller", "voice": voice, "difficulty": difficulty}
    policy = get_response_policy(ir, profile)
    return PromptBuilder().build_system(
        profile=profile,
        intent=ir,
        policy=policy,
        knowledge=knowledge or KnowledgeContext.unknown(),
        emotion_state="neutral",
        emotion_intensity="low",
    )


def test_teammate_and_coach_are_distinct():
    assert "TEAMMATE" in _build(Intent.GAME_TACTICS, "TEAMMATE")
    assert "COACH" in _build(Intent.GAME_TACTICS, "COACH")


def test_demon_is_depth_not_fake_facts():
    text = _build(Intent.GAME_TACTICS, difficulty="Demon")
    assert "DEMON" in text
    assert "Never fabricate" in text


def test_current_request_requires_verified_current():
    text = _build(Intent.META_CURRENT)
    assert "requires VERIFIED_CURRENT" in text


def test_knowledge_injection_contains_source_and_date():
    knowledge = KnowledgeContext(
        facts=[KnowledgeFact("FOV: 115", "test-source", "2025-12-11", KnowledgeConfidence.DATED_SOURCE)],
        source="test-source",
        last_updated="2025-12-11",
        freshness="dated",
        confidence=KnowledgeConfidence.DATED_SOURCE,
    )
    text = _build(Intent.GAME_SETTINGS, knowledge=knowledge)
    assert "test-source" in text
    assert "2025-12-11" in text
    assert "FOV: 115" in text
