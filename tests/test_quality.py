from app.services.brain.knowledge_context import KnowledgeContext
from app.services.brain.quality import currentness_blocked_response


def test_currentness_gate_is_explicit():
    text = currentness_blocked_response(KnowledgeContext.unknown())
    assert "Актуальность не подтверждена" in text
    assert "не буду выдавать" in text
