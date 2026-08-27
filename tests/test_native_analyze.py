from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.crown_core.api import NativeCrownAPI
from app.crown_core.contracts import CrownAnalyzeEvidence, CrownAnalyzeItem, CrownAnalyzeReport, CrownPrincipal, CrownTurnRequest, CrownSurface
from app.crown_core.service import CrownCore
from app.services.analyze import AnalyzeFailure, ImageAnalyzeService
from app.services.storage.memory import InMemoryStore


OWNER_ONE = UUID("11111111-1111-4111-8111-111111111111")
OWNER_TWO = UUID("22222222-2222-4222-8222-222222222222")
PRINCIPAL_ONE = CrownPrincipal(OWNER_ONE, "apple", str(uuid4()), 1001)
PRINCIPAL_TWO = CrownPrincipal(OWNER_TWO, "apple", str(uuid4()), 2002)


def image_bytes(size=(96, 72), image_format="PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (31, 24, 12)).save(output, format=image_format)
    return output.getvalue()


class Profiles:
    def get(self, owner):
        canonical = OWNER_ONE if int(owner) == 1001 else OWNER_TWO
        return {
            "black_crown_user_id": str(canonical),
            "game": "Warzone",
            "playstyle": "strategic",
            "_chat_id": int(owner),
        }


class Conversation:
    def __init__(self):
        self.server_context = None

    def reply(self, **kwargs):
        self.server_context = kwargs.get("server_context")
        return "Разбор продолжен."


class Analyzer:
    max_bytes = 8 * 1024 * 1024

    def analyze(self, *, report_id, question, **kwargs):
        return CrownAnalyzeReport(
            report_id=report_id,
            created_at="2026-08-26T12:00:00Z",
            media_kind="image",
            summary="На скриншоте видна игровая сборка.",
            findings=(CrownAnalyzeItem("Сборка", "Показаны реальные компоненты.", "loadout"),),
            recommendations=(CrownAnalyzeItem("Проверить роль", "Сопоставь сборку с режимом.", "strategy"),),
            warnings=(),
            evidence=(CrownAnalyzeEvidence("В центре виден экран сборки.", "центр"),),
            follow_up_suggestions=("Обсудить компромиссы",),
            question=question,
        )


class Authenticator:
    async def authenticate(self, authorization):
        if authorization == "Bearer one":
            return PRINCIPAL_ONE
        if authorization == "Bearer two":
            return PRINCIPAL_TWO
        raise HTTPException(status_code=401, detail="invalid_session")


def api_client(analyzer=None):
    store = InMemoryStore()
    conversation = Conversation()
    core = CrownCore(
        conversation=conversation,
        store=store,
        profiles=Profiles(),
        analyzer=analyzer or Analyzer(),
    )
    api = NativeCrownAPI(
        settings=SimpleNamespace(
            supabase_url="",
            supabase_service_role_key="",
            analyze_image_max_bytes=8 * 1024 * 1024,
        ),
        core=core,
        store=store,
        authenticator=Authenticator(),
    )
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app), core, conversation


def analyze(client, *, token="one", payload=None, mime="image/png", report_id=None):
    return client.post(
        "/api/v1/crown/analyze/image",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(report_id or uuid4()),
            "X-Crown-Correlation-ID": str(uuid4()),
        },
        data={"question": "Что можно улучшить?", "locale": "ru-RU"},
        files={"image": ("screen.png", payload or image_bytes(), mime)},
    )


def test_authenticated_analysis_persists_and_retrieves_owner_scoped_report():
    client, _, _ = api_client()
    report_id = uuid4()
    response = analyze(client, report_id=report_id)
    assert response.status_code == 200
    assert response.json()["id"] == str(report_id)
    assert response.json()["provenance"]["response_source"] == "REAL_BACKEND"

    listing = client.get("/api/v1/crown/analyze/reports", headers={"Authorization": "Bearer one"})
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()["reports"]] == [str(report_id)]
    detail = client.get(
        f"/api/v1/crown/analyze/reports/{report_id}",
        headers={"Authorization": "Bearer one"},
    )
    assert detail.status_code == 200
    assert detail.json()["summary"] == "На скриншоте видна игровая сборка."


def test_analysis_requires_authentication_and_rejects_unsupported_media():
    client, _, _ = api_client()
    denied = client.post(
        "/api/v1/crown/analyze/image",
        files={"image": ("screen.png", image_bytes(), "image/png")},
    )
    assert denied.status_code == 401
    unsupported = analyze(client, mime="application/pdf")
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"] == "unsupported_media"


@pytest.mark.parametrize(
    ("code", "status"),
    [("rate_limited", 429), ("service_unavailable", 503), ("analysis_failed", 503)],
)
def test_typed_provider_failures_are_mapped_without_provider_detail(code, status):
    class FailingAnalyzer(Analyzer):
        def analyze(self, **kwargs):
            raise AnalyzeFailure(code)

    client, _, _ = api_client(analyzer=FailingAnalyzer())
    response = analyze(client)
    assert response.status_code == status
    assert response.json() == {"detail": code}


def test_cross_user_report_access_is_rejected_without_revealing_owner():
    client, _, _ = api_client()
    report_id = uuid4()
    assert analyze(client, report_id=report_id).status_code == 200
    response = client.get(
        f"/api/v1/crown/analyze/reports/{report_id}",
        headers={"Authorization": "Bearer two"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "report_not_found"


def test_analysis_idempotency_replays_without_duplicate_report():
    client, _, _ = api_client()
    report_id = uuid4()
    first = analyze(client, report_id=report_id)
    second = analyze(client, report_id=report_id)
    assert first.status_code == second.status_code == 200
    assert second.headers["x-crown-replay"] == "1"
    listing = client.get("/api/v1/crown/analyze/reports", headers={"Authorization": "Bearer one"})
    assert len(listing.json()["reports"]) == 1


def test_continue_turn_resolves_typed_report_context_server_side():
    client, core, conversation = api_client()
    report_id = uuid4()
    assert analyze(client, report_id=report_id).status_code == 200
    request = CrownTurnRequest(
        principal=PRINCIPAL_ONE,
        surface=CrownSurface.IOS,
        session_id=uuid4(),
        turn_id=uuid4(),
        text="Продолжим разбор.",
        locale="ru-RU",
        route="multimodal",
        analysis_report_id=report_id,
    )
    result = core.execute_turn(request)
    assert result.display_text == "Разбор продолжен."
    assert conversation.server_context["analysis_report"]["id"] == str(report_id)
    assert conversation.server_context["analysis_report"]["summary"]


class FakeCompletionClient:
    def __init__(self, content=None, failure=None):
        self.content = content
        self.failure = failure
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def provider_service(content=None, failure=None, max_bytes=8 * 1024 * 1024):
    client = FakeCompletionClient(content=content, failure=failure)
    return ImageAnalyzeService(
        api_key="server-only-test-key",
        model="fixture-vision",
        max_bytes=max_bytes,
        client_factory=lambda: client,
    )


def test_structured_provider_response_is_bounded_and_unknown_category_normalized():
    service = provider_service(
        content='{"summary":"Реальный разбор","findings":[{"title":"Факт","detail":"Виден интерфейс","category":"invented"}],"recommendations":[],"warnings":[],"evidence":[{"observation":"Слева видна панель"}],"follow_up_suggestions":[]}'
    )
    report = service.analyze(
        payload=image_bytes(),
        declared_mime="image/png",
        profile={"game": "Warzone", "black_crown_user_id": str(OWNER_ONE)},
        question="Что видно?",
        locale="ru-RU",
        report_id=uuid4(),
    )
    assert report.summary == "Реальный разбор"
    assert report.findings[0].category == "unknown"
    assert report.evidence[0].observation == "Слева видна панель"


@pytest.mark.parametrize(
    ("payload", "mime", "code"),
    [
        (b"not-an-image", "image/png", "image_decode_failed"),
        (image_bytes(), "image/gif", "unsupported_media"),
        (b"x" * 700_001, "image/png", "image_too_large"),
    ],
)
def test_media_validation_failures_are_typed(payload, mime, code):
    service = provider_service(content='{"summary":"ok"}', max_bytes=700_000)
    with pytest.raises(AnalyzeFailure) as failure:
        service.analyze(
            payload=payload,
            declared_mime=mime,
            profile={},
            question="",
            locale="ru-RU",
            report_id=uuid4(),
        )
    assert failure.value.code == code


def test_invalid_provider_response_and_provider_failure_are_typed():
    for service, expected in [
        (provider_service(content="not-json"), "invalid_response"),
        (provider_service(failure=RuntimeError("secret provider detail")), "analysis_failed"),
    ]:
        with pytest.raises(AnalyzeFailure) as failure:
            service.analyze(
                payload=image_bytes(),
                declared_mime="image/png",
                profile={},
                question="",
                locale="ru-RU",
                report_id=uuid4(),
            )
        assert failure.value.code == expected
