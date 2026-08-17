from app.release import APP_VERSION, RELEASE_CONTRACT


def test_phase19_release_metadata():
    assert APP_VERSION == "19.0.0"
    assert RELEASE_CONTRACT == "bco-adaptive-mission-control-v19"
