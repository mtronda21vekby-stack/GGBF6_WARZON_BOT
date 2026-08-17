from app.services.missions import AdaptiveMissionService, MissionConflict


def test_mission_package_exports_public_service():
    assert AdaptiveMissionService is not None
    assert issubclass(MissionConflict, ValueError)
