from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import Request

from app.crown_core.action_stream import proposals_from_provider_metadata, realtime_action_payload
from app.crown_core.actions import ActionValidationFailure
from app.crown_core.api import NativeCrownAPI, PROTOCOL_VERSION, _sse
from app.crown_core.contracts import CrownTurnRequest
from app.crown_core.response import SpokenSentenceAccumulator
from app.crown_core.runtime import ActiveTurn


log = logging.getLogger("crown.native.actions")


class ActionNativeCrownAPI(NativeCrownAPI):
    """Native API variant that projects validated CROWN actions into SSE.

    The language model/provider only supplies untrusted proposal metadata. This
    boundary never executes an action. It normalizes through the closed
    crown-actions-v1 registry and emits only validated semantic proposals for
    the device-side policy/confirmation/execution runtime.
    """

    async def _event_stream(
        self,
        request: CrownTurnRequest,
        control: ActiveTurn,
        http_request: Request,
    ) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        accumulator = SpokenSentenceAccumulator()
        sequence = 0
        emitted: list[dict[str, Any]] = []
        provider_action_metadata: dict[str, Any] | None = None

        def envelope(event_type: str, **fields: Any) -> dict[str, Any]:
            nonlocal sequence
            sequence += 1
            return {
                "schemaVersion": 1,
                "protocolVersion": PROTOCOL_VERSION,
                "type": event_type,
                "sessionID": str(request.session_id),
                "turnID": {"rawValue": str(request.turn_id)},
                "eventID": str(uuid4()),
                "sequence": sequence,
                "timestamp": time.time(),
                **fields,
            }

        def put(event: dict[str, Any]) -> None:
            if not queue.full():
                queue.put_nowait(event)

        def on_partial(cumulative: str, meta: dict[str, Any]) -> None:
            nonlocal provider_action_metadata
            if control.cancellation.is_set():
                raise asyncio.CancelledError()

            # Preserve only the action metadata envelope. Validation remains at
            # the crown-actions-v1 normalization boundary below. Do not log or
            # otherwise expose proposal arguments here.
            if isinstance(meta, dict) and "action_proposals" in meta:
                provider_action_metadata = {
                    "action_proposals": meta.get("action_proposals")
                }

            display_delta, speech = accumulator.update(cumulative)
            if display_delta:
                loop.call_soon_threadsafe(put, envelope("textDelta", text=display_delta))
            for segment in speech:
                loop.call_soon_threadsafe(put, envelope("spokenContent", text=segment))

        initial = [
            envelope("routeSelected", route=request.route),
            envelope("turnStarted"),
            envelope(
                "performanceIntent",
                performance={
                    "communicativeIntent": "explain",
                    "tone": "focused",
                    "energy": "restrained",
                    "emphasis": 0.35,
                    "confidence": {"value": 0.9},
                    "urgency": 0.1,
                    "focusTarget": "user",
                },
            ),
        ]
        for event in initial:
            emitted.append(event)
            yield _sse(event)

        task = asyncio.create_task(
            self.core.execute_turn_async(request, on_partial=on_partial),
            name=f"crown-native-{request.session_id}-{request.turn_id}",
        )
        completed = False
        try:
            while not task.done():
                if control.cancellation.is_set() or await http_request.is_disconnected():
                    control.cancellation.set()
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    if control.cancellation.is_set():
                        task.cancel()
                        break
                    continue
                emitted.append(event)
                yield _sse(event)
                queue.task_done()

            if control.cancellation.is_set():
                task.cancel()
                yield _sse(envelope("turnCancelled", failureCode="cancelled"))
                return

            result = await task
            while not queue.empty():
                event = queue.get_nowait()
                emitted.append(event)
                yield _sse(event)
                queue.task_done()

            display_delta, speech, _ = accumulator.finish(result.display_text)
            if display_delta:
                event = envelope("textDelta", text=display_delta)
                emitted.append(event)
                yield _sse(event)
            for segment in speech:
                event = envelope("spokenContent", text=segment)
                emitted.append(event)
                yield _sse(event)

            action_metadata = (
                result.action_metadata
                if isinstance(result.action_metadata, dict)
                else provider_action_metadata
            )
            try:
                proposals = proposals_from_provider_metadata(
                    action_metadata,
                    source_turn_id=request.turn_id,
                )
            except ActionValidationFailure as failure:
                # A malformed model proposal must never poison a valid text
                # response and must never reach an executor. Fail closed by
                # dropping the entire action set for this turn.
                log.warning(
                    "native action proposal rejected surface=ios turn=%s code=%s",
                    request.turn_id,
                    failure.code,
                )
                proposals = ()

            for proposal in proposals:
                projected = realtime_action_payload(proposal)
                event = envelope(
                    "actionProposal",
                    actionProposal=projected["actionProposal"],
                )
                emitted.append(event)
                yield _sse(event)

            event = envelope("turnCompleted")
            emitted.append(event)
            yield _sse(event)
            completed = True
        except asyncio.CancelledError:
            control.cancellation.set()
            task.cancel()
            raise
        except Exception as exc:
            log.warning(
                "native turn failed surface=ios session=%s turn=%s error=%s",
                request.session_id,
                request.turn_id,
                type(exc).__name__,
            )
            yield _sse(envelope("turnFailed", failureCode="provider_unavailable"))
        finally:
            if not task.done():
                control.cancellation.set()
                task.cancel()
            self.turns.finish(control, emitted if completed else None)
