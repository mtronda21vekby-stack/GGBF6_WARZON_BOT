from app.services.session_cycle import CrownSessionCycleService


class Store:
    def __init__(self):
        self.rows = []

    def list_progression_events(self, chat_id, limit=200):
        return list(reversed(self.rows))[:limit]

    def add_progression_event(self, chat_id, event):
        self.rows.append(dict(event))


def test_prepare_is_idempotent_until_cycle_closes():
    store = Store()
    service = CrownSessionCycleService(store)
    mission = {"id": "m1", "title": "TEST", "focus": "decision"}
    first = service.start(42, mission)
    second = service.start(42, mission)
    assert first["crown_session_id"] == second["crown_session_id"]
    assert len([x for x in store.rows if x.get("status") == "prepared"]) == 1

    service.close(42, first["crown_session_id"], "m1", "clean")
    third = service.start(42, mission)
    assert third["crown_session_id"] != first["crown_session_id"]


def test_current_cycle_is_scoped_by_mission():
    store = Store()
    service = CrownSessionCycleService(store)
    a = service.start(42, {"id": "m1", "title": "ONE"})
    service.close(42, a["crown_session_id"], "m1", "mixed")
    b = service.start(42, {"id": "m2", "title": "TWO"})
    assert service.current(42, "m1") is None
    assert service.current(42, "m2")["crown_session_id"] == b["crown_session_id"]


def test_after_action_contract_uses_only_session_scoped_vod_source():
    source = open("app/services/after_action.py", "r", encoding="utf-8").read()
    assert "linked_vod_evidence" in source
    assert "operator_mission_evidence" in source
    assert "crown_session_id" in source
    assert "vod_must_match_session_and_mission" in source
    assert "latest_vod_evidence" not in source


def test_vod_fusion_persists_session_id_without_auto_completion():
    source = open("app/services/vod/mission_evidence.py", "r", encoding="utf-8").read()
    assert "CrownSessionCycleService" in source
    assert '"crown_session_id"' in source
    assert '"does_not_complete_mission": True' in source
    assert "session_link_authority" in source
