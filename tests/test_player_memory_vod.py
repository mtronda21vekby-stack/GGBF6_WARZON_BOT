from app.services.player_memory.service import PlayerMemoryService
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore
from app.services.vod.service import VODAnalysisResult, VODMistake


def test_high_confidence_vod_findings_enter_player_memory():
    store = InMemoryStore()
    profiles = ProfileService(store=store)
    service = PlayerMemoryService(store=store, profiles=profiles)

    result = VODAnalysisResult(
        summary="Сильная позиция, но повторный пик был читаемым.",
        mistakes=[
            VODMistake(
                key="open_repeek",
                label="Повторный пик без смены угла",
                category="positioning",
                confidence=0.9,
            ),
            VODMistake(
                key="uncertain",
                label="Возможная поздняя ротация",
                category="decision",
                confidence=0.4,
            ),
        ],
        next_drill="break LOS -> новый угол",
        sampled_timestamps=["00:12", "00:30"],
        model="test-model",
    )

    service.observe_vod(
        chat_id=7,
        profile=profiles.get(7),
        result=result,
        trusted=True,
    )

    mistakes = store.list_recurring_mistakes(7)
    assert "Повторный пик без смены угла" in mistakes
    assert "Возможная поздняя ротация" not in mistakes

    episodes = store.list_episodes(7)
    assert episodes[0]["kind"] == "vod_sampled_frames"

    progression = store.list_progression_events(7)
    assert progression[0]["type"] == "vod_review"

    profile = profiles.get(7)
    assert "VOD sampled-frames" in profile["last_session_summary"]
