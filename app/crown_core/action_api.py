from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.crown_core.action_planner import CrownActionPlanner
from app.crown_core.action_results import CrownActionResultFailure, record_action_result
from app.crown_core.action_stream import proposals_from_provider_metadata, realtime_action_payload
from app.crown_core.actions import ActionValidationFailure
from app.crown_core.api import NativeCrownAPI, PROTOCOL_VERSION, _sse
from app.crown_core.contracts import CrownTurnRequest
from app.crown_core.memory_actions import CrownMemoryActionFailure, forget_canonical_memory_field
from app.crown_core.response import SpokenSentenceAccumulator
from app.crown_core.runtime import ActiveTurn


log = logging.getLogger("crown.native.actions")


class ActionNativeCrownAPI(NativeCrownAPI):
    """Native API variant that projects validated CROWN actions into SSE.

    Provider/model metadata is always untrusted. A small deterministic planner
    may propose only explicit, high-confidence V1 actions when provider-native
    tool metadata is absent. Both sources still pass through the exact same
    closed crown-actions-v1 registry before anything reaches the device. This
    boundary never executes an action on model authority.
    """

    def _bind_routes(self) -> None:
        super()._bind_routes()

        @self.router.delete("/brain/{field}")
        async def forget_brain_field(
            field: str,
            authorization: str | None = Header(default=None),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ):
            principal = await self._principal(authorization)
            normalized = str(field or "").strip().lower()
            try:
                mutation_key = UUID(str(idempotency_key or ""))
            except ValueError:
                raise HTTPException(status_code=400, detail="idempotency_key_required") from None

            operation = f"brain.forget.{normalized}"
            replay_state, replay = self.mutations.begin(
                principal.black_crown_user_id,
                mutation_key,
                operation,
            )
            if replay_state == "replay" and replay is not None:
                return JSONResponse(replay, headers={"X-Crown-Replay": "1"})
            if replay_state == "in_progress":
                raise HTTPException(status_code=409, detail="idempotency_in_progress")

            try:
                snapshot = await asyncio.to_thread(
                    forget_canonical_memory_field,
                    self.core,
                    principal,
                    normalized,
                )
            except CrownMemoryActionFailure:
                self.mutations.abort(
                    principal.black_crown_user_id,
                    mutation_key,
                    operation,
                )
                raise HTTPException(status_code=400, detail="invalid_brain_field") from None
            except Exception:
                self.mutations.abort(
                    principal.black_crown_user_id,
                    mutation_key,
                    operation,
                )
                log.exception(
                    "canonical memory forget failed owner=%s field=%s",
                    principal.black_crown_user_id,
                    normalized,
                )
                raise HTTPException(status_code=503, detail="brain_mutation_failed") from None

            result = {
                "schema_version": 1,
                "black_crown_user_id": str(principal.black_crown_user_id),
                "forgotten_field": normalized,
                **snapshot,
            }
            self.mutations.finish(
                principal.black_crown_user_id,
                mutation_key,
                operation,
                result,
            )
            return JSONResponse(result, headers={"X-Crown-Replay": "0"})

        @self.router.post("/actions/result")
        async def action_result(
            body: dict[str, Any],
            authorization: str | None = Header(default=None),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ):
            principal = await self._principal(authorization)
            try:
                proposal_id = UUID(str(body.get("proposal_id") or ""))
                mutation_key = UUID(str(idempotency_key or ""))
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid_action_result_identifier") from None
            if proposal_id != mutation_key:
                raise HTTPException(status_code=400, detail="action_result_idempotency_mismatch")

            operation = "action.result"
            replay_state, replay = self.mutations.begin(
                principal.black_crown_user_id,
                mutation_key,
                operation,
            )
            if replay_state == "replay" and replay is not None:
                return JSONResponse(replay, headers={"X-Crown-Replay": "1"})
            if replay_state == "in_progress":
                raise HTTPException(status_code=409, detail="idempotency_in_progress")

            try:
                recorded = await asyncio.to_thread(
                    record_action_result,
                    self.core,
                    principal,
                    body,
                )
            except CrownActionResultFailure as failure:
                self.mutations.abort(
                    principal.black_crown_user_id,
                    mutation_key,
                    operation,
                )
                status = 404 if failure.code == "analysis_report_not_found" else 400
                raise HTTPException(status_code=status, detail=failure.code) from None
            except Exception:
                self.mutations.abort(
                    principal.black_crown_user_id,
                    mutation_key,
                    operation,
                )
                log.exception(
                    "action result persistence failed owner=%s proposal=%s",
                    principal.black_crown_user_id,
                    proposal_id,
                )
                raise HTTPException(status_code=503, detail="action_result_unavailable") from None

            result = {
                "schema_version": 1,
                "accepted": True,
                "proposal_id": recorded["proposal_id"],
                "action_id": recorded["action_id"],
                "recorded_at": recorded.get("recorded_at"),
            }
            self.mutations.finish(
                principal.black_crown_user_id,
                mutation_key,
                operation,
                result,
            )
            return JSONResponse(result, headers={"X-Crown-Replay": "0"})

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
            if not action_metadata:
                action_metadata = CrownActionPlanner().propose(
                    text=request.text,
                    source_turn_id=request.turn_id,
                    analysis_report_id=request.analysis_report_id,
                )

            try:
                proposals = proposals_from_provider_metadata(
                    action_metadata,
                    source_turn_id=request.turn_id,
                )
            except ActionValidationFailure as failure:
                rejection_code = str(failure)[:80] or "invalid_action_proposal"
                log.warning(
                    "native action proposal rejected surface=ios turn=%s code=%s",
                    request.turn_id,
                    rejection_code,
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
