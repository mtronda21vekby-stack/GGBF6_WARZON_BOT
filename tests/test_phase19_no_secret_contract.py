from inspect import signature

from app.services.missions.service import AdaptiveMissionService


def test_mission_service_constructor_has_no_provider_secret():
    params = set(signature(AdaptiveMissionService).parameters)
    assert params.isdisjoint({"api_key", "openai_api_key", "token", "service_role_key"})
