from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.crown_core.contracts import CrownCoreFailure, CrownPrincipal, CrownSurface, CrownTurnRequest
from app.crown_core.response import SpokenSentenceAccumulator
from app.crown_core.runtime import ActiveTurn, ActiveTurnRegistry
from app.crown_core.skills import CrownSkillRegistry


log = logging.getLogger("crown.native")
PROTOCOL_VERSION = "crown-realtime-v1"


class SupabaseNativeAuthenticator:
    """Validates the user JWT with GAME Auth, then resolves ownership server-side."""

    def __init__(self, *, settings: Any, core: Any) -> None:
        self._url = str(getattr(settings, "supabase_url", "") or "").rstrip("/")
        self._server_key = str(getattr(settings, "supabase_service_role_key", "") or "")
        self._core = core

    async def authenticate(self, authorization: str) -> CrownPrincipal:
        token = _bearer(authorization)
        if not self._url or not self._server_key:
            raise HTTPException(status_code=503, detail="identity_unavailable")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
                response = await client.get(
                    f"{self._url}/auth/v1/user",
                    headers={"apikey": self._server_key, "Authorization": f"Bearer {token}"},
                )
        except Exception:
            raise HTTPException(status_code=503, detail="identity_unavailable") from None
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="invalid_session")
        try:
            user = response.json()
            subject = str(user.get("id") or "")
            UUID(subject)
            app_metadata = user.get("app_metadata") if isinstance(user.get("app_metadata"), dict) else {}
            providers = set(str(item) for item in (app_metadata.get("providers") or []) if item)
            if app_metadata.get("provider"):
                providers.add(str(app_metadata["provider"]))
        except Exception:
            raise HTTPException(status_code=401, detail="invalid_session") from None
        if "apple" not in providers:
            raise HTTPException(status_code=403, detail="apple_identity_required")
        principal = await asyncio.to_thread(
            self._core.principal_for_authenticated_identity,
            "apple",
            subject,
        )
        if principal is None:
            raise HTTPException(status_code=403, detail="canonical_link_required")
        return principal


class NativeSessionBody(BaseModel):
    session_id: str | dict[str, Any] | None = None


class NativeTurnBody(BaseModel):
    schemaVersion: int = Field(default=1)
    sessionID: str | dict[str, Any]
    turnID: str | dict[str, Any]
    observation: dict[str, Any]
    route: str = "fast"
    budget: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    conversationLocaleIdentifier: str | None = None
    personality: dict[str, Any] = Field(default_factory=dict)


class NativeCancelBody(BaseModel):
    session_id: str | dict[str, Any]
    turn_id: str | dict[str, Any]


class NativeBrainPatch(BaseModel):
    patch: dict[str, Any]


class NativeCrownAPI:
    def __init__(
        self,
        *,
        settings: Any,
        core: Any,
        store: Any,
        authenticator: Any | None = None,
        turns: ActiveTurnRegistry | None = None,
        skills: CrownSkillRegistry | None = None,
    ) -> None:
        self.core = core
        self.store = store
        self.authenticator = authenticator or SupabaseNativeAuthenticator(settings=settings, core=core)
        self.turns = turns or ActiveTurnRegistry()
        self.skills = skills or CrownSkillRegistry()
        self.router = APIRouter(prefix="/api/v1/crown", tags=["CROWN native"])
        self._bind_routes()

    async def _principal(self, authorization: str | None) -> CrownPrincipal:
        if not authorization:
            raise HTTPException(status_code=401, detail="authentication_required")
        return await self.authenticator.authenticate(authorization)

    def _bind_routes(self) -> None:
        @self.router.post("/bootstrap")
        async def bootstrap(authorization: str | None = Header(default=None)):
            principal = await self._principal(authorization)
            brain = await asyncio.to_thread(self.core.brain_snapshot, principal)
            entitlement_reader = getattr(self.store, "list_canonical_entitlements", None)
            entitlements = []
            if callable(entitlement_reader):
                entitlements = await asyncio.to_thread(entitlement_reader, str(principal.black_crown_user_id))
            return {
                "schema_version": 1,
                "black_crown_user_id": str(principal.black_crown_user_id),
                "player_brain": brain,
                "entitlements": entitlements,
                "capabilities": list(self.skills.capabilities(CrownSurface.IOS)),
                "server": {"protocol_version": PROTOCOL_VERSION},
            }

        @self.router.post("/session")
        async def session(body: NativeSessionBody, authorization: str | None = Header(default=None)):
            principal = await self._principal(authorization)
            session_id = _uuid(body.session_id) if body.session_id is not None else uuid4()
            return {
                "schema_version": 1,
                "session_id": str(session_id),
                "black_crown_user_id": str(principal.black_crown_user_id),
                "protocol_version": PROTOCOL_VERSION,
            }

        @self.router.post("/turn")
        async def turn(
            body: NativeTurnBody,
            request: Request,
            authorization: str | None = Header(default=None),
        ):
            principal = await self._principal(authorization)
            parsed = _turn_request(body, principal)
            replay = self.turns.replay(principal.black_crown_user_id, parsed.session_id, parsed.turn_id)
            if replay is not None:
                return StreamingResponse(
                    _replay(replay),
                    media_type="text/event-stream",
                    headers=_stream_headers(str(parsed.turn_id), replay=True),
                )
            try:
                control = self.turns.start(principal.black_crown_user_id, parsed.session_id, parsed.turn_id)
            except CrownCoreFailure as failure:
                status = 409 if failure.code == "turn_in_progress" else 403
                raise HTTPException(status_code=status, detail=failure.code) from None
            return StreamingResponse(
                self._event_stream(parsed, control, request),
                media_type="text/event-stream",
                headers=_stream_headers(str(parsed.turn_id)),
            )

        @self.router.post("/cancel")
        async def cancel(body: NativeCancelBody, authorization: str | None = Header(default=None)):
            principal = await self._principal(authorization)
            try:
                cancelled = self.turns.cancel(
                    principal.black_crown_user_id,
                    _uuid(body.session_id),
                    _uuid(body.turn_id),
                )
            except CrownCoreFailure as failure:
                raise HTTPException(status_code=403, detail=failure.code) from None
            return {"ok": True, "cancelled": cancelled}

        @self.router.get("/brain")
        async def brain(authorization: str | None = Header(default=None)):
            principal = await self._principal(authorization)
            snapshot = await asyncio.to_thread(self.core.brain_snapshot, principal)
            return {"black_crown_user_id": str(principal.black_crown_user_id), **snapshot}

        @self.router.patch("/brain")
        async def patch_brain(
            body: NativeBrainPatch,
            authorization: str | None = Header(default=None),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ):
            principal = await self._principal(authorization)
            try:
                UUID(str(idempotency_key or ""))
            except ValueError:
                raise HTTPException(status_code=400, detail="idempotency_key_required") from None
            try:
                snapshot = await asyncio.to_thread(self.core.patch_brain, principal, body.patch)
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid_brain_patch") from None
            return {"black_crown_user_id": str(principal.black_crown_user_id), **snapshot}

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

        def on_partial(cumulative: str, _meta: dict[str, Any]) -> None:
            if control.cancellation.is_set():
                raise asyncio.CancelledError()
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


def _turn_request(body: NativeTurnBody, principal: CrownPrincipal) -> CrownTurnRequest:
    if body.schemaVersion != 1:
        raise HTTPException(status_code=409, detail="protocol_mismatch")
    text = str(body.observation.get("content") or "").strip()
    if not text or len(text) > 6000:
        raise HTTPException(status_code=400, detail="invalid_request")
    route = str(body.route or "fast")
    if route not in {"fast", "standard", "deep", "local", "multimodal", "specialized"}:
        raise HTTPException(status_code=400, detail="invalid_request")
    personality = body.personality if isinstance(body.personality, dict) else {}
    if personality and str(personality.get("identifier") or "black-crown-live") != "black-crown-live":
        raise HTTPException(status_code=400, detail="invalid_personality")
    messages = body.context.get("messages") if isinstance(body.context, dict) else []
    safe_context = tuple(item for item in messages[-20:] if isinstance(item, dict)) if isinstance(messages, list) else ()
    return CrownTurnRequest(
        principal=principal,
        surface=CrownSurface.IOS,
        session_id=_uuid(body.sessionID),
        turn_id=_uuid(body.turnID),
        text=text,
        locale=str(body.conversationLocaleIdentifier or "ru-RU")[:32],
        route=route,
        client_context=safe_context,
    )


def _bearer(value: str) -> str:
    prefix = "Bearer "
    if not value.startswith(prefix) or len(value) <= len(prefix):
        raise HTTPException(status_code=401, detail="authentication_required")
    token = value[len(prefix):].strip()
    if len(token) < 20 or len(token) > 8192:
        raise HTTPException(status_code=401, detail="invalid_session")
    return token


def _uuid(value: Any) -> UUID:
    raw = value.get("rawValue") if isinstance(value, dict) else value
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid_request") from None


def _sse(payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {payload.get('eventID', '')}\nevent: {payload.get('type', 'message')}\ndata: {data}\n\n".encode()


async def _replay(events: tuple[dict, ...]) -> AsyncIterator[bytes]:
    for event in events:
        yield _sse(event)


def _stream_headers(turn_id: str, *, replay: bool = False) -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "X-Content-Type-Options": "nosniff",
        "X-Crown-Protocol": PROTOCOL_VERSION,
        "X-Crown-Turn-ID": turn_id,
        "X-Crown-Replay": "1" if replay else "0",
    }
