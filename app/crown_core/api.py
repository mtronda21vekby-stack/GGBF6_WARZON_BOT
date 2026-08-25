from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, NoReturn
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.crown_core.contracts import CrownCoreFailure, CrownPrincipal, CrownSurface, CrownTurnRequest
from app.crown_core.response import SpokenSentenceAccumulator
from app.crown_core.runtime import ActiveTurn, ActiveTurnRegistry, MutationReplayRegistry
from app.crown_core.skills import CrownSkillRegistry
from app.crown_core.voice import (
    VOICE_PROTOCOL_VERSION,
    ActiveVoiceSynthesis,
    NativeVoiceRegistry,
    native_voice_profile,
    pcm_s16_chunks,
    voice_profile_for,
)
from app.services.identity.apple_link import AppleIdentityLinkRejected


log = logging.getLogger("crown.native")
PROTOCOL_VERSION = "crown-realtime-v1"


class SupabaseNativeAuthenticator:
    """Validates the user JWT with GAME Auth, then resolves ownership server-side."""

    def __init__(self, *, settings: Any, core: Any) -> None:
        self._url = str(getattr(settings, "supabase_url", "") or "").rstrip("/")
        self._server_key = str(getattr(settings, "supabase_service_role_key", "") or "")
        self._core = core

    async def authenticate_identity(self, authorization: str) -> str:
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
        return subject

    async def authenticate(self, authorization: str) -> CrownPrincipal:
        subject = await self.authenticate_identity(authorization)
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


class NativeVoiceBody(BaseModel):
    schemaVersion: int = Field(default=1)
    sessionID: str | dict[str, Any]
    turnID: str | dict[str, Any]
    speechGenerationID: str | dict[str, Any]
    requestID: str | dict[str, Any]
    segmentIndex: int = Field(default=0, ge=0, le=512)
    locale: str = Field(default="ru-RU", min_length=2, max_length=24)
    text: str = Field(min_length=1, max_length=4096)


class NativeVoiceCancelBody(BaseModel):
    sessionID: str | dict[str, Any]
    speechGenerationID: str | dict[str, Any]


class NativeCrownAPI:
    def __init__(
        self,
        *,
        settings: Any,
        core: Any,
        store: Any,
        authenticator: Any | None = None,
        turns: ActiveTurnRegistry | None = None,
        mutations: MutationReplayRegistry | None = None,
        skills: CrownSkillRegistry | None = None,
        voice: Any | None = None,
        voice_generations: NativeVoiceRegistry | None = None,
        usage_guard: Any | None = None,
        account_links: Any | None = None,
    ) -> None:
        self.core = core
        self.store = store
        self.authenticator = authenticator or SupabaseNativeAuthenticator(settings=settings, core=core)
        self.turns = turns or ActiveTurnRegistry()
        self.mutations = mutations or MutationReplayRegistry()
        self.skills = skills or CrownSkillRegistry()
        self.voice = voice
        self.voice_generations = voice_generations or NativeVoiceRegistry()
        self.voice_generation_max_characters = max(
            500,
            min(int(getattr(settings, "voice_duplex_max_chars", 1800) or 1800), 3000),
        )
        self.voice_generation_max_segments = 32
        self.voice_stream_keepalive_s = 4.0
        self.usage_guard = usage_guard
        self.account_links = account_links
        self.router = APIRouter(prefix="/api/v1/crown", tags=["CROWN native"])
        self._bind_routes()

    async def _principal(self, authorization: str | None) -> CrownPrincipal:
        if not authorization:
            raise HTTPException(status_code=401, detail="authentication_required")
        return await self.authenticator.authenticate(authorization)

    async def _apple_identity(self, authorization: str | None) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="authentication_required")
        authenticate_identity = getattr(self.authenticator, "authenticate_identity", None)
        if not callable(authenticate_identity):
            raise HTTPException(status_code=503, detail="identity_unavailable")
        return str(await authenticate_identity(authorization))

    def _bind_routes(self) -> None:
        @self.router.post("/account-link/start")
        async def start_account_link(
            authorization: str | None = Header(default=None),
            x_crown_correlation_id: str | None = Header(default=None, alias="X-Crown-Correlation-ID"),
        ):
            subject = await self._apple_identity(authorization)
            if self.account_links is None or not bool(getattr(self.account_links, "configured", False)):
                raise HTTPException(status_code=503, detail="account_link_unavailable")
            request_id = _safe_request_id(x_crown_correlation_id)
            try:
                challenge = await self.account_links.start(subject)
            except AppleIdentityLinkRejected as failure:
                _raise_account_link_failure(failure.reason)
            except Exception:
                log.exception("account link start failed request=%s", request_id)
                raise HTTPException(status_code=503, detail="account_link_unavailable") from None
            log.info("account link started method=telegram request=%s link=%s", request_id, challenge.link_id)
            return {
                "schema_version": 1,
                "link_id": str(challenge.link_id),
                "verification_url": challenge.verification_url,
                "expires_at": challenge.expires_at,
                "link_method": "telegram",
            }

        @self.router.get("/account-link/{link_id}/status")
        async def account_link_status(
            link_id: UUID,
            authorization: str | None = Header(default=None),
            x_crown_correlation_id: str | None = Header(default=None, alias="X-Crown-Correlation-ID"),
        ):
            subject = await self._apple_identity(authorization)
            if self.account_links is None:
                raise HTTPException(status_code=503, detail="account_link_unavailable")
            request_id = _safe_request_id(x_crown_correlation_id)
            try:
                result = await self.account_links.status(link_id=link_id, apple_subject=subject)
            except AppleIdentityLinkRejected as failure:
                _raise_account_link_failure(failure.reason)
            except Exception:
                log.exception("account link status failed request=%s link=%s", request_id, link_id)
                raise HTTPException(status_code=503, detail="account_link_unavailable") from None
            return {
                "schema_version": 1,
                "link_id": str(link_id),
                "status": result.status,
                "expires_at": result.expires_at,
            }

        @self.router.delete("/account-link/{link_id}")
        async def cancel_account_link(
            link_id: UUID,
            authorization: str | None = Header(default=None),
        ):
            subject = await self._apple_identity(authorization)
            if self.account_links is None:
                raise HTTPException(status_code=503, detail="account_link_unavailable")
            try:
                result = await self.account_links.cancel(link_id=link_id, apple_subject=subject)
            except AppleIdentityLinkRejected as failure:
                _raise_account_link_failure(failure.reason)
            except Exception:
                raise HTTPException(status_code=503, detail="account_link_unavailable") from None
            return {"schema_version": 1, "link_id": str(link_id), "status": result.status}

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

        @self.router.get("/skills/{skill_id}")
        async def read_skill(
            skill_id: str,
            authorization: str | None = Header(default=None),
            cursor: str | None = Query(default=None, max_length=32),
            limit: int = Query(default=20, ge=1, le=50),
            x_crown_request_id: str | None = Header(default=None, alias="X-Crown-Request-ID"),
        ):
            principal = await self._principal(authorization)
            self._enforce_usage(principal, "skill")
            try:
                skill_request_id = UUID(str(x_crown_request_id or ""))
            except ValueError:
                skill_request_id = uuid4()
            if not self.skills.permits_read(skill_id, CrownSurface.IOS):
                raise HTTPException(status_code=404, detail="capability_unavailable")
            try:
                result = await asyncio.to_thread(
                    self.core.skill_result,
                    principal,
                    skill_id,
                    cursor=cursor,
                    limit=limit,
                )
            except ValueError:
                raise HTTPException(status_code=404, detail="capability_unavailable") from None
            log.info(
                "native skill complete surface=ios owner=%s skill=%s request=%s",
                principal.black_crown_user_id,
                skill_id,
                skill_request_id,
            )
            return {
                "schema_version": 1,
                "request_id": str(skill_request_id),
                "capability": skill_id,
                "black_crown_user_id": str(principal.black_crown_user_id),
                **result.projection(),
            }

        @self.router.get("/voice/profile")
        async def voice_profile(authorization: str | None = Header(default=None)):
            await self._principal(authorization)
            if self.voice is None or not bool(getattr(self.voice, "enabled", False)):
                raise HTTPException(status_code=503, detail="speech_synthesis_unavailable")
            return voice_profile_for(self.voice)

        @self.router.post("/voice/synthesize")
        async def synthesize_voice(
            body: NativeVoiceBody,
            authorization: str | None = Header(default=None),
        ):
            principal = await self._principal(authorization)
            if body.schemaVersion != 1:
                raise HTTPException(status_code=409, detail="protocol_mismatch")
            if self.voice is None or not bool(getattr(self.voice, "enabled", False)):
                raise HTTPException(status_code=503, detail="speech_synthesis_unavailable")
            session_id = _uuid(body.sessionID)
            turn_id = _uuid(body.turnID)
            generation_id = _uuid(body.speechGenerationID)
            request_id = _uuid(body.requestID)
            try:
                control = self.voice_generations.start(
                    principal.black_crown_user_id,
                    session_id,
                    turn_id,
                    generation_id,
                    request_id,
                    segment_index=body.segmentIndex,
                    text_length=len(body.text),
                    maximum_segments=self.voice_generation_max_segments,
                    maximum_characters=self.voice_generation_max_characters,
                    on_generation_start=lambda: self._enforce_usage(principal, "voice"),
                )
            except CrownCoreFailure as failure:
                if failure.code == "ownership_mismatch":
                    status = 403
                elif failure.code == "voice_generation_too_large":
                    status = 413
                elif failure.code == "voice_capacity_exhausted":
                    status = 503
                else:
                    status = 409
                raise HTTPException(status_code=status, detail=failure.code) from None
            return StreamingResponse(
                self._voice_stream(body, principal, control),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-store",
                    "X-Accel-Buffering": "no",
                    "X-Content-Type-Options": "nosniff",
                    "X-Crown-Protocol": VOICE_PROTOCOL_VERSION,
                    "X-Crown-Speech-Generation-ID": str(generation_id),
                },
            )

        @self.router.post("/voice/cancel")
        async def cancel_voice(
            body: NativeVoiceCancelBody,
            authorization: str | None = Header(default=None),
        ):
            principal = await self._principal(authorization)
            try:
                cancelled = self.voice_generations.cancel(
                    principal.black_crown_user_id,
                    _uuid(body.sessionID),
                    _uuid(body.speechGenerationID),
                )
            except CrownCoreFailure as failure:
                raise HTTPException(status_code=403, detail=failure.code) from None
            return {"ok": True, "cancelled": cancelled}

        @self.router.patch("/brain")
        async def patch_brain(
            body: NativeBrainPatch,
            authorization: str | None = Header(default=None),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        ):
            principal = await self._principal(authorization)
            try:
                mutation_key = UUID(str(idempotency_key or ""))
            except ValueError:
                raise HTTPException(status_code=400, detail="idempotency_key_required") from None
            replay_state, replay = self.mutations.begin(
                principal.black_crown_user_id,
                mutation_key,
                "brain.patch",
            )
            if replay_state == "replay" and replay is not None:
                return JSONResponse(replay, headers={"X-Crown-Replay": "1"})
            if replay_state == "in_progress":
                raise HTTPException(status_code=409, detail="idempotency_in_progress")
            try:
                snapshot = await asyncio.to_thread(self.core.patch_brain, principal, body.patch)
            except ValueError:
                self.mutations.abort(principal.black_crown_user_id, mutation_key, "brain.patch")
                raise HTTPException(status_code=400, detail="invalid_brain_patch") from None
            except Exception:
                self.mutations.abort(principal.black_crown_user_id, mutation_key, "brain.patch")
                raise
            result = {"black_crown_user_id": str(principal.black_crown_user_id), **snapshot}
            self.mutations.finish(principal.black_crown_user_id, mutation_key, "brain.patch", result)
            return JSONResponse(result, headers={"X-Crown-Replay": "0"})

    def _enforce_usage(self, principal: CrownPrincipal, category: str) -> None:
        if self.usage_guard is None:
            return
        decision = self.usage_guard.check(principal.legacy_owner_id, category)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={"Retry-After": str(decision.retry_after_s)},
            )

    async def _voice_stream(
        self,
        body: NativeVoiceBody,
        principal: CrownPrincipal,
        control: ActiveVoiceSynthesis,
    ) -> AsyncIterator[bytes]:
        task = asyncio.current_task()
        if task is not None:
            self.voice_generations.attach(control, task)
        sequence = 0
        artifact = None
        synthesis_task: asyncio.Task[Any] | None = None

        def envelope(event_type: str, **fields: Any) -> dict[str, Any]:
            nonlocal sequence
            sequence += 1
            return {
                "schema_version": 1,
                "protocol_version": VOICE_PROTOCOL_VERSION,
                "type": event_type,
                "session_id": str(control.session_id),
                "turn_id": str(control.turn_id),
                "speech_generation_id": str(control.generation_id),
                "request_id": str(control.request_id),
                "event_id": str(uuid4()),
                "sequence": sequence,
                "timestamp": time.time(),
                "segment_index": int(body.segmentIndex),
                **fields,
            }

        completed = False
        try:
            log.info(
                "native voice start surface=ios owner=%s session=%s turn=%s generation=%s request=%s",
                principal.black_crown_user_id,
                control.session_id,
                control.turn_id,
                control.generation_id,
                control.request_id,
            )
            profile = await asyncio.to_thread(
                native_voice_profile,
                principal,
                self.core,
                body.locale,
            )
            # Cloud synthesis produces a complete WAV before PCM framing. Keep
            # the authenticated SSE transport alive while that bounded server
            # operation runs; otherwise a healthy provider response slightly
            # beyond the client's idle timeout is misclassified as unavailable.
            synthesis_task = asyncio.create_task(self.voice.synthesize_wave(body.text, profile))
            keepalive_count = 0
            while not synthesis_task.done():
                done, _ = await asyncio.wait(
                    {synthesis_task},
                    timeout=max(0.05, float(self.voice_stream_keepalive_s)),
                )
                if not done:
                    keepalive_count += 1
                    yield b": crown-voice-keepalive\n\n"
            artifact = synthesis_task.result()
            log.info(
                "native voice synthesis ready surface=ios generation=%s request=%s keepalives=%s",
                control.generation_id,
                control.request_id,
                keepalive_count,
            )
            yield _sse(
                envelope(
                    "voice.started",
                    profile_id="black-crown-canonical-v1",
                    quality=artifact.quality,
                    spoken_length=len(artifact.spoken_text),
                )
            )
            chunks = iter(pcm_s16_chunks(artifact.path))
            current = next(chunks, None)
            while current is not None:
                following = next(chunks, None)
                yield _sse(
                    envelope(
                        "voice.audio",
                        **current,
                        is_final=following is None,
                    )
                )
                current = following
                await asyncio.sleep(0)
            completed = True
            yield _sse(envelope("voice.completed", quality=artifact.quality, is_final=True))
            log.info(
                "native voice complete surface=ios session=%s turn=%s generation=%s request=%s",
                control.session_id,
                control.turn_id,
                control.generation_id,
                control.request_id,
            )
        except asyncio.CancelledError:
            log.info(
                "native voice cancelled surface=ios session=%s turn=%s generation=%s request=%s",
                control.session_id,
                control.turn_id,
                control.generation_id,
                control.request_id,
            )
            yield _sse(envelope("voice.cancelled", failure_code="cancelled", is_final=True))
        except ValueError:
            yield _sse(
                envelope(
                    "voice.failed",
                    failure_code="invalid_spoken_content",
                    is_final=True,
                )
            )
        except Exception as exc:
            log.warning(
                "native voice failed request=%s error=%s",
                control.request_id,
                type(exc).__name__,
            )
            yield _sse(
                envelope(
                    "voice.failed",
                    failure_code="speech_synthesis_unavailable",
                    is_final=True,
                )
            )
        finally:
            if synthesis_task is not None and not synthesis_task.done():
                synthesis_task.cancel()
                try:
                    await synthesis_task
                except (asyncio.CancelledError, Exception):
                    pass
            if artifact is not None:
                artifact.cleanup()
            self.voice_generations.finish(control, completed=completed)

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


def _safe_request_id(value: str | None) -> UUID:
    try:
        return UUID(str(value or ""))
    except ValueError:
        return uuid4()


def _raise_account_link_failure(reason: str) -> NoReturn:
    if reason in {"apple_identity_conflict", "challenge_conflict"}:
        raise HTTPException(status_code=409, detail="account_link_conflict")
    if reason == "apple_identity_already_linked":
        raise HTTPException(status_code=409, detail="account_link_already_completed")
    if reason in {"link_expired", "invalid_or_expired_code"}:
        raise HTTPException(status_code=410, detail="account_link_expired")
    if reason in {"link_cancelled", "link_not_found"}:
        raise HTTPException(status_code=404, detail="account_link_not_found")
    if reason in {"invalid_apple_identity", "invalid_telegram_identity"}:
        raise HTTPException(status_code=403, detail="invalid_identity_provider")
    raise HTTPException(status_code=403, detail="account_link_rejected")


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
    event_id = payload.get("eventID") or payload.get("event_id") or ""
    return f"id: {event_id}\nevent: {payload.get('type', 'message')}\ndata: {data}\n\n".encode()


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
