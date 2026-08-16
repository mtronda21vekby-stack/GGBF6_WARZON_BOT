from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.prompt_builder import PromptBuilder
from app.services.brain.response_policy import get_response_policy


def test_persistent_player_context_is_injected_without_internal_tokens():
    intent = IntentResult(Intent.PLAYER_PROGRESS, 0.99, needs_player_memory=True)
    profile = {"game": "Warzone", "voice": "COACH", "difficulty": "Pro"}
    policy = get_response_policy(intent, profile)
    system = PromptBuilder().build_system(
        profile=profile,
        intent=intent,
        policy=policy,
        knowledge=KnowledgeContext.unknown(),
        emotion_state="neutral",
        emotion_intensity="low",
        player_context={
            **profile,
            "memory_summary": "Цель: меньше поздних ротаций",
            "top_mistakes": [{"label": "Поздняя ротация", "count": 4}],
            "derived_intelligence": {"trends": {"kills": {"delta": 1.2}}},
            "_context_token": "must-never-be-rendered",
        },
    )
    assert "Поздняя ротация" in system
    assert "delta" in system
    assert "must-never-be-rendered" not in system
