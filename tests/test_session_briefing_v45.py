import asyncio

import app.services.session_briefing as briefing_module
from app.services.brain.knowledge_context import KnowledgeConfidence, KnowledgeContext, KnowledgeFact
from app.services.session_briefing import SessionBriefingService


CANONICAL = "11111111-1111-1111-1111-111111111111"


class Store:
    def resolve_telegram_identity(self, telegram_user_id):
        return {"black_crown_user_id": CANONICAL, "identity_status": "active", "account_status": "active"}
    def get_summary(self, chat_id): return "Aggressive controller player"
    def get_derived_intelligence(self, chat_id): return {"trends": {}}
    def list_mistake_stats(self, chat_id): return [{"label": "late rotation", "count": 4}]
    def list_training_sessions(self, chat_id): return []
    def list_progression_events(self, chat_id, *args): return []
    def list_episodes(self, chat_id, *args): return []
    def stats(self, chat_id): return {"backend": "test"}


class Profiles:
    def get(self, chat_id):
        return {"game": "Warzone", "input": "Controller", "platform": "Xbox", "difficulty": "Pro", "_black_crown_user_id": CANONICAL}


class Entitlements:
    async def get_status(self, telegram_user_id):
        class Status:
            linked = True
            premium = False
            entitlements = ()
            linked_at = None
        return Status()


def test_prepare_session_keeps_official_and_player_evidence_separate(monkeypatch):
    official = KnowledgeContext(
        facts=[KnowledgeFact("Official document: Warzone Patch Notes", "https://www.callofduty.com/patchnotes/x", "2026-08-19", KnowledgeConfidence.VERIFIED_CURRENT), KnowledgeFact("Weapon damage adjusted.", "https://www.callofduty.com/patchnotes/x", "2026-08-19", KnowledgeConfidence.VERIFIED_CURRENT)],
        source="https://www.callofduty.com/patchnotes/x",
        last_updated="2026-08-19",
        freshness="live_official",
        confidence=KnowledgeConfidence.VERIFIED_CURRENT,
    )
    monkeypatch.setattr(briefing_module._OFFICIAL, "query", lambda request: official)
    data = asyncio.run(SessionBriefingService(store=Store(), profiles=Profiles(), entitlements=Entitlements()).prepare(chat_id=42, telegram_user_id=42))
    assert data["schema"] == "crown-war-room-briefing-v1"
    assert data["identity"]["black_crown_user_id"] == CANONICAL
    assert data["official_intel"]["confidence"] == "VERIFIED_CURRENT"
    assert data["official_intel"]["source"].startswith("https://www.callofduty.com/")
    assert data["personal_meta"]["summary"] == "Aggressive controller player"
    assert data["squad_context"]["status"] == "UNKNOWN"
    assert data["truth"]["official_meta_ranking_claimed"] is False
    assert data["truth"]["unknown_squad_not_inferred"] is True


def test_prepare_session_does_not_fake_current_intel(monkeypatch):
    monkeypatch.setattr(briefing_module._OFFICIAL, "query", lambda request: KnowledgeContext.unknown())
    data = asyncio.run(SessionBriefingService(store=Store(), profiles=Profiles(), entitlements=Entitlements()).prepare(chat_id=42, telegram_user_id=42))
    assert data["official_intel"]["confidence"] == "UNKNOWN"
    assert data["official_intel"]["facts"] == []
    assert data["truth"]["official_patch_facts_only"] is True
