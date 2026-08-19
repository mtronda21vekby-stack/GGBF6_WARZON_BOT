from types import SimpleNamespace

from app.services.vod.engagements import VODEngagementIntelligenceService


class Store:
    def __init__(self): self.events = []
    def add_progression_event(self, chat_id, event): self.events.append(dict(event))
    def add_episode(self, chat_id, event): pass


def item(ts, category="decision", confidence=.8):
    return SimpleNamespace(
        timestamp=ts,
        observation="Player is visible near cover",
        decision="Re-peek same line",
        issue="Repeated exposure",
        correction="Reset angle before re-engaging",
        category=category,
        confidence=confidence,
    )


def test_engagements_are_sampled_frame_only_and_session_scoped():
    store = Store()
    result = SimpleNamespace(timeline=[item(f"00:{i:02d}") for i in range(15)], limitations="Sampled frames only")
    event = VODEngagementIntelligenceService(store).build(
        chat_id=7, result=result, crown_session_id="cs_123", mission_id="m_9"
    )
    assert event["type"] == "vod_engagement_intelligence"
    assert event["crown_session_id"] == "cs_123"
    assert event["mission_id"] == "m_9"
    assert event["engagement_count"] == 12
    assert all(x["sampled_frame_only"] is True for x in event["engagements"])
    assert all(x["continuous_sequence_claimed"] is False for x in event["engagements"])
    assert all(x["first_damage"] is None for x in event["engagements"])
    assert event["truth_contract"]["mission_auto_complete"] is False
