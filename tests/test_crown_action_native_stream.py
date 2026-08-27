from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.crown_core.action_api import ActionNativeCrownAPI
from app.crown_core.contracts import (
    CrownPrincipal,
    CrownSurface,
    CrownTurnRequest,
    CrownTurnResult,
)
from app.crown_core.runtime import ActiveTurn, ActiveTurnRegistry


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


class _Core:
    def __init__(self, metadata):
        self.metadata = metadata

    async def execute_turn_async(self, request, *, on_partial=None):
        if on_partial is not None:
            on_partial("Готово.", self.metadata)
        return CrownTurnResult(display_text="Готово.", spoken_text="Готово.")


def _request(text: str = "Открой анализ", analysis_report_id=None) -> CrownTurnRequest:
    user_id = uuid4()
    return CrownTurnRequest(
        principal=CrownPrincipal(user_id, "apple", str(uuid4()), 77),
        surface=CrownSurface.IOS,
        session_id=uuid4(),
        turn_id=uuid4(),
        text=text,
        locale="ru-RU",
        route="fast",
        analysis_report_id=analysis_report_id,
    )


def _api(metadata):
    api = ActionNativeCrownAPI.__new__(ActionNativeCrownAPI)
    api.core = _Core(metadata)
    api.turns = ActiveTurnRegistry()
    return api


def _control(request: CrownTurnRequest) -> ActiveTurn:
    return ActiveTurn(
        request.principal.black_crown_user_id,
        request.session_id,
        request.turn_id,
    )


async def _events(api, request):
    result = []
    async for chunk in api._event_stream(request, _control(request), _ConnectedRequest()):
        text = chunk.decode("utf-8")
        data_line = next(line for line in text.splitlines() if line.startswith("data: "))
        result.append(json.loads(data_line.removeprefix("data: ")))
    return result


@pytest.mark.asyncio
async def test_native_stream_emits_valid_action_before_completion():
    request = _request()
    proposal_id = uuid4()
    report_id = uuid4()
    events = await _events(
        _api(
            {
                "action_proposals": [
                    {
                        "proposal_id": str(proposal_id),
                        "action_id": "analyze.open_report",
                        "arguments": {"report_id": str(report_id)},
                        "rationale": "Открыть уже принадлежащий пользователю отчёт.",
                        "correlation_id": str(uuid4()),
                    }
                ]
            }
        ),
        request,
    )

    types = [event["type"] for event in events]
    assert "actionProposal" in types
    assert types.index("actionProposal") < types.index("turnCompleted")
    action = events[types.index("actionProposal")]["actionProposal"]
    assert action["protocol_version"] == "crown-actions-v1"
    assert action["proposal_id"] == str(proposal_id)
    assert action["source_turn_id"] == str(request.turn_id)
    assert action["action_id"] == "analyze.open_report"
    assert action["arguments"] == {"report_id": str(report_id)}


@pytest.mark.asyncio
async def test_native_stream_drops_unknown_action_but_keeps_text_turn():
    request = _request(text="Расскажи о моей текущей тренировке")
    events = await _events(
        _api(
            {
                "action_proposals": [
                    {
                        "proposal_id": str(uuid4()),
                        "action_id": "shell.execute",
                        "arguments": {"command": "rm -rf /"},
                        "rationale": "not allowed",
                        "correlation_id": str(uuid4()),
                    }
                ]
            }
        ),
        request,
    )

    types = [event["type"] for event in events]
    assert "actionProposal" not in types
    assert "textDelta" in types
    assert types[-1] == "turnCompleted"


@pytest.mark.asyncio
async def test_native_stream_drops_duplicate_action_set_fail_closed():
    request = _request(text="Расскажи о профиле")
    proposal_id = uuid4()
    raw = {
        "proposal_id": str(proposal_id),
        "action_id": "app.navigate",
        "arguments": {"destination": "brain"},
        "rationale": "Открыть профиль.",
        "correlation_id": str(uuid4()),
    }
    events = await _events(
        _api({"action_proposals": [raw, dict(raw)]}),
        request,
    )

    types = [event["type"] for event in events]
    assert "actionProposal" not in types
    assert types[-1] == "turnCompleted"


@pytest.mark.asyncio
async def test_native_stream_deterministically_plans_explicit_navigation_when_provider_has_no_action():
    request = _request(text="Открой BRAIN")
    events = await _events(_api({}), request)
    types = [event["type"] for event in events]
    assert "actionProposal" in types
    action = events[types.index("actionProposal")]["actionProposal"]
    assert action["action_id"] == "app.navigate"
    assert action["arguments"] == {"destination": "brain"}
    assert action["source_turn_id"] == str(request.turn_id)
    assert types.index("actionProposal") < types.index("turnCompleted")


@pytest.mark.asyncio
async def test_native_stream_deterministically_plans_unambiguous_relative_reminder():
    request = _request(text="Напомни через 2 часа проверить сборку")
    events = await _events(_api({}), request)
    types = [event["type"] for event in events]
    assert "actionProposal" in types
    action = events[types.index("actionProposal")]["actionProposal"]
    assert action["action_id"] == "reminder.create"
    assert action["arguments"]["schedule"] == {"kind": "relative", "seconds": 7200}
    assert "проверить сборку" in action["arguments"]["title"].lower()


@pytest.mark.asyncio
async def test_native_stream_ambiguous_reminder_remains_text_only():
    request = _request(text="Напомни завтра вечером проверить сборку")
    events = await _events(_api({}), request)
    types = [event["type"] for event in events]
    assert "actionProposal" not in types
    assert "textDelta" in types
    assert types[-1] == "turnCompleted"


@pytest.mark.asyncio
async def test_native_stream_without_explicit_action_request_is_unchanged():
    request = _request(text="Что мне тренировать сегодня?")
    events = await _events(_api({}), request)
    types = [event["type"] for event in events]
    assert "actionProposal" not in types
    assert "textDelta" in types
    assert types[-1] == "turnCompleted"
