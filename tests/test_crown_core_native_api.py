from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.crown_core.api import NativeCrownAPI, PROTOCOL_VERSION, SupabaseNativeAuthenticator
from app.crown_core.contracts import CrownPrincipal, CrownSurface, CrownTurnResult
from app.crown_core.response import SpokenSentenceAccumulator, spoken_text
from app.crown_core.runtime import ActiveTurnRegistry, MutationReplayRegistry
from app.crown_core.service import CrownCore
from app.crown_core.skills import CrownSkillRegistry
from app.services.conversation.service import ConversationService


OWNER = UUID("11111111-1111-4111-8111-111111111111")
PRINCIPAL = CrownPrincipal(OWNER, "apple", str(uuid4()), 8275036156)


class FakeAuthenticator:
    def __init__(self, principal=PRINCIPAL, failure: HTTPException | None = None):
        self.principal = principal
        self.failure = failure
        self.seen = []

    async def authenticate(self, authorization):
        self.seen.append(authorization)
        if self.failure:
            raise self.failure
        return self.principal


class FakeAuthResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeAuthHTTPClient:
    response = FakeAuthResponse(401, {})

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self.response


class FakeStore:
    def list_canonical_entitlements(self, owner):
        assert owner == str(OWNER)
        return [{"entitlement_key": "pro", "status": "active"}]

    def list_training_sessions(self, owner):
        assert owner == PRINCIPAL.legacy_owner_id
        return [{"focus": "aim", "chat_id": owner, "source": "approved"}]


class FakeCore:
    def __init__(self):
        self.turns = []
        self.patches = []

    def brain_snapshot(self, principal):
        assert principal == PRINCIPAL
        return {"profile": {"game": "Warzone"}, "summary": "same brain", "derived": {}}

    def patch_brain(self, principal, patch):
        assert principal == PRINCIPAL
        self.patches.append({key: value for key, value in patch.items() if key == "training_focus"})
        return self.brain_snapshot(principal)

    def read_skill(self, principal, identifier):
        assert principal == PRINCIPAL
        return {"fixture": identifier}

    async def execute_turn_async(self, request, *, on_partial=None):
        self.turns.append(request)
        on_partial("Первое предложение. ", {"phase": "generating"})
        on_partial("Первое предложение. Второе предложение.", {"phase": "final"})
        return CrownTurnResult(
            display_text="Первое предложение. Второе предложение.",
            spoken_text="Первое предложение. Второе предложение.",
        )


def app_client(*, auth=None, core=None, registry=None):
    app = FastAPI()
    api = NativeCrownAPI(
        settings=SimpleNamespace(supabase_url="", supabase_service_role_key=""),
        core=core or FakeCore(),
        store=FakeStore(),
        authenticator=auth or FakeAuthenticator(),
        turns=registry,
    )
    app.include_router(api.router)
    return TestClient(app), api


def envelope(session_id, turn_id, text="Расскажи коротко"):
    return {
        "schemaVersion": 1,
        "sessionID": {"rawValue": str(session_id)},
        "turnID": {"rawValue": str(turn_id)},
        "observation": {"content": text, "modality": "voiceTranscript"},
        "route": "fast",
        "budget": {},
        "context": {"messages": []},
        "conversationLocaleIdentifier": "ru-RU",
        "personality": {"identifier": "black-crown-live", "revision": 1},
    }


def sse_payloads(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_native_bootstrap_returns_only_server_resolved_canonical_identity():
    client, _ = app_client()
    response = client.post("/api/v1/crown/bootstrap", headers={"Authorization": "Bearer fixture"})
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "black_crown_user_id": str(OWNER),
        "player_brain": {"profile": {"game": "Warzone"}, "summary": "same brain", "derived": {}},
        "entitlements": [{"entitlement_key": "pro", "status": "active"}],
        "capabilities": [
            "conversation",
            "player_brain_read",
            "game_intel_read",
            "loadout_read",
            "training_summary_read",
            "history_summary_read",
        ],
        "server": {"protocol_version": PROTOCOL_VERSION},
    }


def test_native_authentication_fails_closed_before_core_access():
    core = FakeCore()
    client, _ = app_client(
        auth=FakeAuthenticator(failure=HTTPException(status_code=401, detail="invalid_session")),
        core=core,
    )
    response = client.post("/api/v1/crown/bootstrap", headers={"Authorization": "Bearer expired"})
    assert response.status_code == 401
    assert core.turns == []


def test_supabase_authenticator_rejects_expired_and_non_apple_sessions(monkeypatch):
    import app.crown_core.api as api_module

    settings = SimpleNamespace(
        supabase_url="https://wqriwhciqvrbhkkiuhxb.supabase.co",
        supabase_service_role_key="server-only-fixture",
    )
    core = SimpleNamespace(principal_for_authenticated_identity=lambda *_: PRINCIPAL)
    authenticator = SupabaseNativeAuthenticator(settings=settings, core=core)
    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeAuthHTTPClient)

    async def scenario():
        FakeAuthHTTPClient.response = FakeAuthResponse(401, {})
        with pytest.raises(HTTPException) as expired:
            await authenticator.authenticate("Bearer " + "x" * 32)
        assert expired.value.status_code == 401
        assert expired.value.detail == "invalid_session"

        FakeAuthHTTPClient.response = FakeAuthResponse(
            200,
            {
                "id": str(uuid4()),
                "app_metadata": {"provider": "email", "providers": ["email"]},
            },
        )
        with pytest.raises(HTTPException) as wrong_provider:
            await authenticator.authenticate("Bearer " + "x" * 32)
        assert wrong_provider.value.status_code == 403
        assert wrong_provider.value.detail == "apple_identity_required"

    asyncio.run(scenario())


def test_supabase_authenticator_resolves_apple_subject_server_side(monkeypatch):
    import app.crown_core.api as api_module

    subject = uuid4()
    seen = []

    def resolve(provider, provider_subject):
        seen.append((provider, provider_subject))
        return PRINCIPAL

    settings = SimpleNamespace(
        supabase_url="https://wqriwhciqvrbhkkiuhxb.supabase.co",
        supabase_service_role_key="server-only-fixture",
    )
    authenticator = SupabaseNativeAuthenticator(
        settings=settings,
        core=SimpleNamespace(principal_for_authenticated_identity=resolve),
    )
    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeAuthHTTPClient)
    FakeAuthHTTPClient.response = FakeAuthResponse(
        200,
        {
            "id": str(subject),
            "app_metadata": {"provider": "apple", "providers": ["apple"]},
        },
    )

    assert asyncio.run(authenticator.authenticate("Bearer " + "x" * 32)) == PRINCIPAL
    assert seen == [("apple", str(subject))]


def test_native_turn_stream_has_typed_ordered_protocol_and_complete_spoken_content():
    session_id, turn_id = uuid4(), uuid4()
    client, api = app_client()
    response = client.post(
        "/api/v1/crown/turn",
        headers={"Authorization": "Bearer fixture"},
        json=envelope(session_id, turn_id),
    )
    assert response.status_code == 200
    events = sse_payloads(response)
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert [event["type"] for event in events] == [
        "routeSelected",
        "turnStarted",
        "performanceIntent",
        "textDelta",
        "spokenContent",
        "textDelta",
        "spokenContent",
        "turnCompleted",
    ]
    assert "".join(event.get("text", "") for event in events if event["type"] == "textDelta") == (
        "Первое предложение. Второе предложение."
    )
    assert " ".join(event.get("text", "") for event in events if event["type"] == "spokenContent") == (
        "Первое предложение. Второе предложение."
    )
    assert all(event["protocolVersion"] == PROTOCOL_VERSION for event in events)
    assert api.core.turns[0].principal.black_crown_user_id == OWNER


def test_completed_turn_replay_is_idempotent_and_does_not_generate_twice():
    session_id, turn_id = uuid4(), uuid4()
    core = FakeCore()
    client, _ = app_client(core=core)
    first = client.post(
        "/api/v1/crown/turn",
        headers={"Authorization": "Bearer fixture"},
        json=envelope(session_id, turn_id),
    )
    second = client.post(
        "/api/v1/crown/turn",
        headers={"Authorization": "Bearer fixture"},
        json=envelope(session_id, turn_id),
    )
    assert first.text == second.text
    assert len(core.turns) == 1
    assert second.headers["x-crown-replay"] == "1"


def test_active_turn_cancellation_is_owner_scoped_and_idempotent():
    registry = ActiveTurnRegistry()
    session_id, turn_id = uuid4(), uuid4()
    control = registry.start(OWNER, session_id, turn_id)
    assert registry.cancel(OWNER, session_id, turn_id) is True
    assert registry.cancel(OWNER, session_id, turn_id) is True
    assert control.cancellation.is_set()
    with pytest.raises(Exception, match="ownership_mismatch"):
        registry.cancel(uuid4(), session_id, turn_id)
    registry.finish(control)
    assert registry.cancel(OWNER, session_id, turn_id) is False


def test_safe_brain_patch_requires_idempotency_and_never_accepts_owner_id():
    core = FakeCore()
    client, _ = app_client(core=core)
    denied = client.patch(
        "/api/v1/crown/brain",
        headers={"Authorization": "Bearer fixture"},
        json={"patch": {"black_crown_user_id": str(uuid4())}},
    )
    assert denied.status_code == 400
    accepted = client.patch(
        "/api/v1/crown/brain",
        headers={"Authorization": "Bearer fixture", "Idempotency-Key": str(uuid4())},
        json={"patch": {"training_focus": "aim", "black_crown_user_id": str(uuid4())}},
    )
    assert accepted.status_code == 200
    assert core.patches == [{"training_focus": "aim"}]


def test_safe_brain_patch_replays_same_idempotency_key_without_duplicate_mutation():
    core = FakeCore()
    client, _ = app_client(core=core)
    key = str(uuid4())
    headers = {"Authorization": "Bearer fixture", "Idempotency-Key": key}
    first = client.patch("/api/v1/crown/brain", headers=headers, json={"patch": {"training_focus": "aim"}})
    second = client.patch("/api/v1/crown/brain", headers=headers, json={"patch": {"training_focus": "movement"}})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.headers["x-crown-replay"] == "0"
    assert second.headers["x-crown-replay"] == "1"
    assert core.patches == [{"training_focus": "aim"}]


def test_mutation_idempotency_rejects_concurrent_duplicate_and_recovers_after_abort():
    registry = MutationReplayRegistry()
    key = uuid4()
    assert registry.begin(OWNER, key, "brain.patch") == ("claimed", None)
    assert registry.begin(OWNER, key, "brain.patch") == ("in_progress", None)
    registry.abort(OWNER, key, "brain.patch")
    assert registry.begin(OWNER, key, "brain.patch") == ("claimed", None)
    registry.finish(OWNER, key, "brain.patch", {"ok": True})
    assert registry.begin(OWNER, key, "brain.patch") == ("replay", {"ok": True})


def test_native_read_skills_are_authenticated_allow_listed_and_owner_scoped():
    client, _ = app_client()
    unauthenticated = client.get("/api/v1/crown/skills/player_brain_read")
    assert unauthenticated.status_code == 401

    response = client.get(
        "/api/v1/crown/skills/training_summary_read",
        headers={"Authorization": "Bearer fixture"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "capability": "training_summary_read",
        "black_crown_user_id": str(OWNER),
        "data": {"fixture": "training_summary_read"},
    }

    denied = client.get(
        "/api/v1/crown/skills/player_brain_write",
        headers={"Authorization": "Bearer fixture"},
    )
    assert denied.status_code == 404
    assert denied.json()["detail"] == "capability_unavailable"


def test_spoken_projection_removes_markup_urls_and_preserves_sentence_order():
    display = "**CROWN**: [смотри](https://example.com) план. `Aim` дальше!"
    assert spoken_text(display) == "CROWN: смотри план. Aim дальше!"
    accumulator = SpokenSentenceAccumulator()
    delta1, speech1 = accumulator.update("Первое. Вто")
    delta2, speech2 = accumulator.update("Первое. Второе.")
    assert delta1 + delta2 == "Первое. Второе."
    assert speech1 + speech2 == ["Первое.", "Второе."]


def test_native_skill_registry_exposes_only_explicit_read_only_core_capabilities():
    assert CrownSkillRegistry().capabilities(CrownSurface.IOS) == (
        "conversation",
        "player_brain_read",
        "game_intel_read",
        "loadout_read",
        "training_summary_read",
        "history_summary_read",
    )


class ConversationProbe:
    def __init__(self):
        self.calls = []

    def reply(self, **kwargs):
        self.calls.append(kwargs)
        return "shared"


class ProfileProbe:
    def get(self, owner):
        return {
            "_chat_id": owner,
            "_context_token": "server",
            "black_crown_user_id": str(OWNER),
        }

    def patch(self, owner, patch):
        pass


class SharedStoreProbe:
    def resolve_canonical_identity(self, provider, subject):
        return {
            "black_crown_user_id": str(OWNER),
            "identity_status": "active",
            "account_status": "active",
            "legacy_owner_id": 8275036156,
        }

    def get(self, owner):
        return [{"role": "assistant", "content": "context"}]

    def get_summary(self, owner):
        return "summary"

    def get_derived_intelligence(self, owner):
        return {}

    def list_training_sessions(self, owner):
        return [{"focus": "aim", "chat_id": owner}]


def test_ios_adapter_enters_same_conversation_core_as_telegram_and_web_compatibility():
    conversation = ConversationProbe()
    core = CrownCore(conversation=conversation, store=SharedStoreProbe(), profiles=ProfileProbe())
    assert core.reply(text="telegram", profile={}, history=[]) == "shared"
    assert core.reply(text="web", profile={}, history=[]) == "shared"
    principal = core.principal_for_authenticated_identity("apple", str(uuid4()))
    assert principal is not None and principal.black_crown_user_id == OWNER
    turn = asyncio.run(
        core.execute_turn_async(
            SimpleNamespace(
                principal=principal,
                text="ios",
            )
        )
    )
    assert turn.display_text == "shared"
    assert [call["text"] for call in conversation.calls] == ["telegram", "web", "ios"]


def test_production_wiring_injects_one_core_into_all_three_surface_adapters():
    source = Path("app/webhook.py").read_text(encoding="utf-8")
    assert "conversation = CrownCore(" in source
    assert "NativeCrownAPI(\n        settings=settings,\n        core=conversation" in source
    assert "Router(tg=tg, brain=conversation" in source
    assert "webapp_bind_runtime(\n                brain=conversation" in source

    contracts = Path("app/crown_core/contracts.py").read_text(encoding="utf-8")
    assert "telegram.Update" not in contracts
    assert "telegram.Message" not in contracts
    assert "fastapi" not in contracts


def test_shared_read_skills_use_only_the_server_resolved_canonical_owner():
    core = CrownCore(conversation=ConversationProbe(), store=SharedStoreProbe(), profiles=ProfileProbe())
    principal = core.principal_for_authenticated_identity("apple", str(uuid4()))
    assert principal is not None
    training = core.read_skill(principal, "training_summary_read")
    assert training == {"sessions": [{"focus": "aim"}]}
    history = core.read_skill(principal, "history_summary_read")
    assert history == {
        "messages": [{"role": "assistant", "content": "context"}],
        "count": 1,
    }


def test_native_adapter_reuses_the_shared_canonical_rate_limit_boundary():
    class DeniedGuard:
        def __init__(self):
            self.calls = []

        def check(self, owner, capability):
            self.calls.append((owner, capability))
            return SimpleNamespace(allowed=False, retry_after_s=7)

    class BrainMustNotRun:
        settings = None

        def __init__(self):
            self.calls = 0

        def reply(self, **kwargs):
            self.calls += 1
            return "must not run"

    class TrustedProfiles(ProfileProbe):
        def get(self, owner):
            return {
                "_chat_id": owner,
                "_context_token": "server",
                "black_crown_user_id": str(OWNER),
            }

        def is_trusted_context(self, profile):
            return profile.get("_context_token") == "server"

    guard = DeniedGuard()
    brain = BrainMustNotRun()
    profiles = TrustedProfiles()
    store = SharedStoreProbe()
    conversation = ConversationService(brain=brain, store=store, profiles=profiles, usage_guard=guard)
    core = CrownCore(conversation=conversation, store=store, profiles=profiles)
    client, _ = app_client(core=core)

    response = client.post(
        "/api/v1/crown/turn",
        headers={"Authorization": "Bearer fixture"},
        json=envelope(uuid4(), uuid4()),
    )
    assert response.status_code == 200
    assert guard.calls == [(PRINCIPAL.legacy_owner_id, "ai")]
    assert brain.calls == 0
    assert "Слишком много AI-запросов" in response.text
