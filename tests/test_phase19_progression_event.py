from app.services.missions.service import MISSION_EVENT_TYPE, MISSION_SOURCE


def test_phase19_progression_event_identifiers_are_explicit():
    assert MISSION_EVENT_TYPE == "adaptive_mission"
    assert MISSION_SOURCE == "adaptive_mission_control_v19"
