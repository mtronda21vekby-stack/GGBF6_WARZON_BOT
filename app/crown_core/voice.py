from __future__ import annotations

import asyncio
import base64
import struct
import threading
import time
import wave
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

from app.crown_core.contracts import CrownCoreFailure, CrownPrincipal


VOICE_PROTOCOL_VERSION = "crown-voice-v1"


@dataclass(frozen=True)
class CrownVoiceProfile:
    profile_id: str = "black-crown-canonical-v1"
    display_name: str = "BLACK CROWN"

    def projection(self, *, high_fidelity: bool, fallback: bool) -> dict[str, Any]:
        languages = ["ru-RU"]
        if high_fidelity:
            languages.append("en-US")
        return {
            "schema_version": 1,
            "protocol_version": VOICE_PROTOCOL_VERSION,
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "supported_languages": languages,
            "presentation": "composed_concise_conversational",
            "provider_capability_class": (
                "high_fidelity_with_local_fallback" if high_fidelity else "local_russian_fallback"
            ),
            "streaming_support": "buffered_pcm_chunks",
            "timing_support": "audio_clock",
            "fallback_profile": "black-crown-local-ru-v1" if fallback else None,
            "output_codecs": ["pcm_s16le"],
            "high_fidelity_available": bool(high_fidelity),
            "local_fallback_available": bool(fallback),
        }


@dataclass
class ActiveVoiceSynthesis:
    owner: UUID
    session_id: UUID
    turn_id: UUID
    generation_id: UUID
    request_id: UUID
    task: asyncio.Task[Any] | None = None


@dataclass
class VoiceGenerationBudget:
    owner: UUID
    turn_id: UUID
    next_segment_index: int
    character_count: int
    updated_at: float
    cancelled: bool = False


class NativeVoiceRegistry:
    """Owner-scoped generation authority for native speech cancellation."""

    def __init__(
        self,
        completed_limit: int = 256,
        generation_limit: int = 1024,
        generation_ttl_s: float = 900.0,
    ) -> None:
        self._lock = threading.RLock()
        self._active: dict[tuple[UUID, UUID], ActiveVoiceSynthesis] = {}
        self._completed: OrderedDict[tuple[UUID, UUID], None] = OrderedDict()
        self._completed_limit = max(16, int(completed_limit))
        self._generations: OrderedDict[tuple[UUID, UUID], VoiceGenerationBudget] = OrderedDict()
        self._generation_limit = max(32, int(generation_limit))
        self._generation_ttl_s = max(30.0, float(generation_ttl_s))

    def start(
        self,
        owner: UUID,
        session_id: UUID,
        turn_id: UUID,
        generation_id: UUID,
        request_id: UUID,
        *,
        segment_index: int = 0,
        text_length: int = 0,
        maximum_segments: int = 32,
        maximum_characters: int = 1800,
        on_generation_start: Any | None = None,
    ) -> ActiveVoiceSynthesis:
        key = (session_id, generation_id)
        request_key = (owner, request_id)
        with self._lock:
            self._prune_generations(time.monotonic())
            if request_key in self._completed:
                raise CrownCoreFailure("voice_request_completed")
            existing = self._active.get(key)
            if existing is not None:
                if existing.owner != owner:
                    raise CrownCoreFailure("ownership_mismatch")
                raise CrownCoreFailure("voice_generation_in_progress")

            now = time.monotonic()
            budget = self._generations.get(key)
            if budget is None:
                if segment_index != 0:
                    raise CrownCoreFailure("voice_segment_out_of_order")
                if callable(on_generation_start):
                    on_generation_start()
                budget = VoiceGenerationBudget(owner, turn_id, 0, 0, now)
                self._generations[key] = budget
            else:
                if budget.owner != owner:
                    raise CrownCoreFailure("ownership_mismatch")
                if budget.turn_id != turn_id:
                    raise CrownCoreFailure("voice_generation_conflict")
                if budget.cancelled:
                    raise CrownCoreFailure("voice_generation_cancelled")
                self._generations.move_to_end(key)

            if segment_index != budget.next_segment_index:
                raise CrownCoreFailure("voice_segment_out_of_order")
            if segment_index >= max(1, int(maximum_segments)):
                raise CrownCoreFailure("voice_generation_too_large")
            next_character_count = budget.character_count + max(0, int(text_length))
            if next_character_count > max(1, int(maximum_characters)):
                raise CrownCoreFailure("voice_generation_too_large")
            budget.next_segment_index += 1
            budget.character_count = next_character_count
            budget.updated_at = now
            control = ActiveVoiceSynthesis(owner, session_id, turn_id, generation_id, request_id)
            self._active[key] = control
            return control

    def attach(self, control: ActiveVoiceSynthesis, task: asyncio.Task[Any]) -> None:
        with self._lock:
            if self._active.get((control.session_id, control.generation_id)) is control:
                control.task = task

    def cancel(self, owner: UUID, session_id: UUID, generation_id: UUID) -> bool:
        with self._lock:
            key = (session_id, generation_id)
            budget = self._generations.get(key)
            if budget is not None:
                if budget.owner != owner:
                    raise CrownCoreFailure("ownership_mismatch")
                budget.cancelled = True
                budget.updated_at = time.monotonic()
            control = self._active.get((session_id, generation_id))
            if control is None:
                return budget is not None
            if control.owner != owner:
                raise CrownCoreFailure("ownership_mismatch")
            task = control.task
        if task is not None:
            task.cancel()
        return True

    def finish(self, control: ActiveVoiceSynthesis, *, completed: bool) -> None:
        with self._lock:
            key = (control.session_id, control.generation_id)
            if self._active.get(key) is control:
                self._active.pop(key, None)
            if completed:
                request_key = (control.owner, control.request_id)
                self._completed[request_key] = None
                self._completed.move_to_end(request_key)
                while len(self._completed) > self._completed_limit:
                    self._completed.popitem(last=False)

    def _prune_generations(self, now: float) -> None:
        expired_before = now - self._generation_ttl_s
        for key, budget in list(self._generations.items()):
            if budget.updated_at >= expired_before:
                continue
            if key not in self._active:
                self._generations.pop(key, None)
        while len(self._generations) >= self._generation_limit:
            victim = next((key for key in self._generations if key not in self._active), None)
            if victim is None:
                raise CrownCoreFailure("voice_capacity_exhausted")
            self._generations.pop(victim, None)


def voice_profile_for(service: Any) -> dict[str, Any]:
    fallback = bool(getattr(service, "_local_fallback_enabled", False) and getattr(service, "backend", None))
    return CrownVoiceProfile().projection(
        high_fidelity=bool(getattr(service, "high_fidelity_active", False)),
        fallback=fallback,
    )


def native_voice_profile(principal: CrownPrincipal, core: Any, locale: str) -> dict[str, Any]:
    source = dict(core.profile_for(principal))
    profile = {
        key: source[key]
        for key in ("voice", "tts_voice", "voice_identity", "difficulty")
        if key in source
    }
    profile["language"] = "en" if str(locale).casefold().startswith("en") else "ru"
    profile["locale"] = locale
    profile["_bco_voice_reply"] = True
    return profile


def pcm_s16_chunks(path: Path, *, chunk_frames: int = 4096) -> Iterator[dict[str, Any]]:
    with wave.open(str(path), "rb") as source:
        channels = int(source.getnchannels())
        sample_rate = int(source.getframerate())
        sample_width = int(source.getsampwidth())
        index = 0
        while True:
            raw = source.readframes(max(256, int(chunk_frames)))
            if not raw:
                break
            if sample_width != 2:
                raw = _linear_pcm_to_s16(raw, sample_width)
            yield {
                "codec": "pcm_s16le",
                "sample_rate": sample_rate,
                "channels": channels,
                "chunk_index": index,
                "audio_base64": base64.b64encode(raw).decode("ascii"),
            }
            index += 1


def _linear_pcm_to_s16(raw: bytes, sample_width: int) -> bytes:
    if sample_width == 1:
        return b"".join(struct.pack("<h", (value - 128) << 8) for value in raw)
    if sample_width in {3, 4}:
        converted = bytearray()
        shift = 8 if sample_width == 3 else 16
        for offset in range(0, len(raw), sample_width):
            sample = raw[offset : offset + sample_width]
            if len(sample) != sample_width:
                break
            value = int.from_bytes(sample, byteorder="little", signed=True) >> shift
            converted.extend(struct.pack("<h", max(-32768, min(32767, value))))
        return bytes(converted)
    raise ValueError("unsupported_pcm_sample_width")
