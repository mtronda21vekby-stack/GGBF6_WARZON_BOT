from app.services.missions.contracts import MISSION_FOCUS_DOMAINS


def test_phase19_focus_domains_are_complete_and_bounded():
    assert MISSION_FOCUS_DOMAINS == {"aim", "movement", "positioning", "decision", "comms"}
