from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crown_core.action_api import ActionNativeCrownAPI
from app.crown_core.action_results import record_issued_action_proposal
from app.crown_core.actions import normalize_action_proposal
from app.crown_core.contracts import CrownPrincipal


class _Store:
    def __init__(self):
        self.episodes: dict[int, list[dict]] = {}

    def list_episodes(self, owner_id: int, _limit: int):
        return list(self.episodes.get(owner_id, []))

    def add_episode(self, owner_id: int, episode: dict):
        self.episodes.setdefault(owner_id, []).append(dict(episode))


class _Core:
    def __init__(self, store: _Store):
        self.store = store
        self.profiles: dict[int, dict[str, str]] = {}

    def profile_for(self, principal: CrownPrincipal):
        return dict(self.profiles.get(principal.legacy_owner_id, {}))

    def analysis_report(self, principal: CrownPrincipal, report_id):
        return None


class _Authenticator:
    def __init__(self, principal: CrownPrincipal):
        self.principal = principal

    async def authenticate(self, _authorization):
        return self.principal

    async def authenticate_identity(self, _authorization):
        return self.principal.provider_subject


def _principal(owner_id: int = 77) -> CrownPrincipal:
    return CrownPrincipal(uuid4(), "apple", str(uuid4()), owner_id)


def _client(principal: CrownPrincipal, core: _Core, store: _Store) -> TestClient:
    app = FastAPI()
    api = ActionNativeCrownAPI(
        settings=SimpleNamespace(supabase_url="", supabase_service_role_key=""),
        core=core,
        store=store,
        authenticator=_Authenticator(principal),
    )
    app.include_router(api.router)
    return TestClient(app)


def _issued_memory_save(core: _Core, principal: CrownPrincipal, value: str = "Top 250"):
    proposal_id = uuid4()
    turn_id = uuid4()
    correlation_id = uuid4()
    proposal = normalize_action_proposal(
        {
            "proposal_id": str(proposal_id),
            "correlation_id": str(correlation_id),
            "action_id": "memory.propose_save",
            "arguments": {"field": "current_goal", "value": value},
            "rationale": "test",
        },
        source_turn_id=turn_id,
    )
    record_issued_action_proposal(core, principal, proposal)
    return proposal


def _body(proposal, *, field="current_goal"):
    return {
        "protocol_version": "crown-actions-v1",
        "proposal_id": str(proposal.proposal_id),
        "action_id": proposal.action_id,
        "source_turn_id": str(proposal.source_turn_id),
        "correlation_id": str(proposal.correlation_id),
        "status": "succeeded",
        "result": {"field": field},
    }


def test_action_result_route_requires_authorization_header():
    principal = _principal()
    store = _Store()
    core = _Core(store)
    client = _client(principal, core, store)

    response = client.post("/api/v1/crown/actions/result", json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "authentication_required"


def test_action_result_route_accepts_verified_effect_and_replays_idempotently():
    principal = _principal()
    store = _Store()
    core = _Core(store)
    proposal = _issued_memory_save(core, principal)
    core.profiles[principal.legacy_owner_id] = {"current_goal": "Top 250"}
    client = _client(principal, core, store)
    headers = {
        "Authorization": "Bearer fixture",
        "Idempotency-Key": str(proposal.proposal_id),
    }

    first = client.post("/api/v1/crown/actions/result", headers=headers, json=_body(proposal))
    replay = client.post("/api/v1/crown/actions/result", headers=headers, json=_body(proposal))

    assert first.status_code == 200
    assert first.headers["X-Crown-Replay"] == "0"
    assert first.json()["accepted"] is True
    assert first.json()["proposal_id"] == str(proposal.proposal_id)
    assert replay.status_code == 200
    assert replay.headers["X-Crown-Replay"] == "1"
    assert replay.json()["proposal_id"] == first.json()["proposal_id"]


def test_action_result_route_rejects_effect_mismatch():
    principal = _principal()
    store = _Store()
    core = _Core(store)
    proposal = _issued_memory_save(core, principal, value="Exact approved value")
    core.profiles[principal.legacy_owner_id] = {"current_goal": "Different value"}
    client = _client(principal, core, store)

    response = client.post(
        "/api/v1/crown/actions/result",
        headers={
            "Authorization": "Bearer fixture",
            "Idempotency-Key": str(proposal.proposal_id),
        },
        json=_body(proposal),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "action_effect_mismatch"


def test_action_result_route_rejects_fabricated_unissued_action():
    principal = _principal()
    store = _Store()
    core = _Core(store)
    proposal = normalize_action_proposal(
        {
            "proposal_id": str(uuid4()),
            "correlation_id": str(uuid4()),
            "action_id": "memory.propose_save",
            "arguments": {"field": "current_goal", "value": "Top 250"},
            "rationale": "test",
        },
        source_turn_id=uuid4(),
    )
    core.profiles[principal.legacy_owner_id] = {"current_goal": "Top 250"}
    client = _client(principal, core, store)

    response = client.post(
        "/api/v1/crown/actions/result",
        headers={
            "Authorization": "Bearer fixture",
            "Idempotency-Key": str(proposal.proposal_id),
        },
        json=_body(proposal),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "action_proposal_not_issued"


def test_action_result_route_rejects_idempotency_key_mismatch():
    principal = _principal()
    store = _Store()
    core = _Core(store)
    proposal = _issued_memory_save(core, principal)
    core.profiles[principal.legacy_owner_id] = {"current_goal": "Top 250"}
    client = _client(principal, core, store)

    response = client.post(
        "/api/v1/crown/actions/result",
        headers={
            "Authorization": "Bearer fixture",
            "Idempotency-Key": str(uuid4()),
        },
        json=_body(proposal),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "action_result_idempotency_mismatch"


def test_action_result_route_cannot_reuse_other_owner_issuance():
    owner = _principal(101)
    attacker = _principal(202)
    store = _Store()
    core = _Core(store)
    proposal = _issued_memory_save(core, owner)
    core.profiles[owner.legacy_owner_id] = {"current_goal": "Top 250"}
    core.profiles[attacker.legacy_owner_id] = {"current_goal": "Top 250"}
    client = _client(attacker, core, store)

    response = client.post(
        "/api/v1/crown/actions/result",
        headers={
            "Authorization": "Bearer attacker",
            "Idempotency-Key": str(proposal.proposal_id),
        },
        json=_body(proposal),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "action_proposal_not_issued"
