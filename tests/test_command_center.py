from __future__ import annotations

from app.services.analytics.command_center import CommandCenterService
from app.services.profiles.service import ProfileService
from app.services.storage.memory import InMemoryStore


def _fixture():
    store = InMemoryStore()
    profiles = ProfileService(store=store)
    profiles.patch(77, {
        "game": "Warzone",
        "platform": "Xbox",
        "input": "Controller",
        "rank": "Diamond",
        "kd": 1.42,
        "current_goal": "улучшить ротации",
        "aim_score": 72,
        # movement/positioning/etc deliberately unknown
        "tts_mode": "AUTO",
    })
    store.add_recurring_mistake(77, "Поздняя ротация")
    store.add_recurring_mistake(77, "Поздняя ротация")
    store.add_training_session(77, {"focus": "positioning", "game": "Warzone", "at": "2026-08-10T10:00:00Z"})
    store.add_progression_event(77, {"type": "match_report", "metrics": {"kills": 6, "placement": 8}, "at": "2026-08-10T11:00:00Z"})
    store.add_progression_event(77, {"type": "match_report", "metrics": {"kills": 9, "placement": 4}, "at": "2026-08-11T11:00:00Z"})
    store.add_episode(77, {
        "kind": "vod_sampled_frames",
        "game": "Warzone",
        "analysis": {"summary": "Потерял сильную позицию ради лишнего килла.", "sampled_timestamps": [12.0, 18.0]},
        "confirmed_mistakes": ["Overpeek from power position"],
        "at": "2026-08-12T11:00:00Z",
    })
    store.set_derived_intelligence(77, {"trends": {"kills": {"previous_avg": 6, "recent_avg": 9, "delta": 3}}})
    store.set_summary(77, "Цель: улучшить ротации. Повторяющиеся ошибки: Поздняя ротация ×2")
    return store, profiles


def test_command_center_uses_evidence_and_preserves_unknown_scores():
    store, profiles = _fixture()
    snap = CommandCenterService(store=store, profiles=profiles).snapshot(77)

    assert snap["profile"]["rank"] == "Diamond"
    assert snap["scores"]["aim"] == 72
    assert snap["scores"]["movement"] is None
    assert snap["scores"]["positioning"] is None
    assert snap["coverage"] > 0


def test_command_center_exposes_real_memory_signals_without_raw_media():
    store, profiles = _fixture()
    snap = CommandCenterService(store=store, profiles=profiles).snapshot(77)

    assert snap["top_mistakes"][0]["count"] == 2
    assert snap["training"][0]["focus"] == "positioning"
    assert [p["value"] for p in snap["metric_series"]["kills"]] == [6, 9]
    assert snap["vod_reviews"][0]["confirmed_mistakes"] == ["Overpeek from power position"]
    assert "raw_video" not in str(snap).lower()


def test_command_center_route_is_before_legacy_static_catchall():
    from app.webhook import create_app

    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    intel_index = paths.index("/webapp/api/intelligence")
    static_index = paths.index("/webapp/{req_path:path}")
    assert intel_index < static_index
