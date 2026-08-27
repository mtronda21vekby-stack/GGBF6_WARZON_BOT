from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Callable
from uuid import UUID

import certifi
import httpx
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.crown_core.contracts import CrownAnalyzeEvidence, CrownAnalyzeItem, CrownAnalyzeReport


class AnalyzeFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _ProviderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="", max_length=180)
    detail: str = Field(default="", max_length=1600)
    category: str = Field(default="general", max_length=48)


class _ProviderEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    observation: str = Field(default="", max_length=1200)
    visible_region: str = Field(default="", max_length=160)


class _ProviderReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(default="", max_length=2400)
    findings: list[_ProviderItem] = Field(default_factory=list, max_length=12)
    recommendations: list[_ProviderItem] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[_ProviderEvidence] = Field(default_factory=list, max_length=12)
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=6)


_CATEGORIES = {
    "general", "interface", "gameplay", "loadout", "statistics", "training",
    "warning", "evidence", "strategy", "quality", "privacy", "unknown",
}


class ImageAnalyzeService:
    """Bounded server-side multimodal adapter owned by Shared CROWN Core."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_bytes: int = 8 * 1024 * 1024,
        max_dimension: int = 2400,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.max_bytes = max(512 * 1024, min(int(max_bytes), 12 * 1024 * 1024))
        self.max_dimension = max(1024, min(int(max_dimension), 4096))
        self.client_factory = client_factory

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> Any:
        if self.client_factory is not None:
            return self.client_factory()
        timeout = httpx.Timeout(connect=20.0, read=90.0, write=60.0, pool=90.0)
        http_client = httpx.Client(
            timeout=timeout,
            verify=certifi.where(),
            headers={"User-Agent": "BLACK-CROWN-ENTITY/analyze-v1"},
        )
        base_url = str(os.getenv("OPENAI_BASE_URL") or "").strip() or None
        return OpenAI(api_key=self.api_key, base_url=base_url, http_client=http_client)

    def normalize_image(self, payload: bytes, declared_mime: str) -> tuple[bytes, int, int]:
        if not payload:
            raise AnalyzeFailure("image_decode_failed")
        if len(payload) > self.max_bytes:
            raise AnalyzeFailure("image_too_large")
        mime = str(declared_mime or "").split(";", 1)[0].strip().lower()
        if mime not in {"image/jpeg", "image/png"}:
            raise AnalyzeFailure("unsupported_media")
        try:
            with Image.open(BytesIO(payload)) as probe:
                actual_format = str(probe.format or "").upper()
                probe.verify()
            if actual_format not in {"JPEG", "PNG"}:
                raise AnalyzeFailure("unsupported_media")
            if (actual_format == "JPEG" and mime != "image/jpeg") or (
                actual_format == "PNG" and mime != "image/png"
            ):
                raise AnalyzeFailure("unsupported_media")
            with Image.open(BytesIO(payload)) as decoded:
                width, height = decoded.size
                if width < 16 or height < 16 or width * height > 40_000_000:
                    raise AnalyzeFailure("image_decode_failed")
                clean = ImageOps.exif_transpose(decoded).convert("RGB")
                clean.thumbnail((self.max_dimension, self.max_dimension), Image.Resampling.LANCZOS)
                width, height = clean.size
                output = BytesIO()
                clean.save(output, format="JPEG", quality=90, optimize=True, progressive=True)
                normalized = output.getvalue()
        except AnalyzeFailure:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
            raise AnalyzeFailure("image_decode_failed") from None
        if not normalized or len(normalized) > self.max_bytes:
            raise AnalyzeFailure("image_too_large")
        return normalized, width, height

    def analyze(
        self,
        *,
        payload: bytes,
        declared_mime: str,
        profile: dict[str, Any],
        question: str,
        locale: str,
        report_id: UUID,
    ) -> CrownAnalyzeReport:
        if not self.enabled:
            raise AnalyzeFailure("service_unavailable")
        normalized, width, height = self.normalize_image(payload, declared_mime)
        language = "Russian" if str(locale).lower().startswith("ru") else "English"
        safe_profile = {
            key: value
            for key, value in dict(profile or {}).items()
            if key in {"game", "mode", "role", "playstyle", "current_goal", "training_focus", "weekly_focus"}
            and isinstance(value, (str, int, float, bool))
        }
        system = (
            "You are CROWN, the canonical BLACK CROWN strategic intelligence for this user. "
            "Analyze only information actually visible in the supplied image. Separate observation from inference. "
            "Never invent player statistics, weapon metadata, certainty values, sources, or coordinates. "
            f"Write user-facing fields in {language}. Return valid JSON only."
        )
        instruction = {
            "task": "analyze_image",
            "question": question or "Perform a useful general analysis of what is visibly present.",
            "image_dimensions": {"width": width, "height": height},
            "canonical_context": safe_profile,
            "output_contract": {
                "summary": "string",
                "findings": [{"title": "string", "detail": "string", "category": "known semantic category"}],
                "recommendations": [{"title": "string", "detail": "string", "category": "known semantic category"}],
                "warnings": ["string"],
                "evidence": [{"observation": "visible fact", "visible_region": "optional natural-language region"}],
                "follow_up_suggestions": ["string"],
            },
            "limits": {"findings": 12, "recommendations": 10, "warnings": 8, "evidence": 12, "follow_up": 6},
        }
        encoded = base64.b64encode(normalized).decode("ascii")
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": json.dumps(instruction, ensure_ascii=False)},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "high"}},
                        ],
                    },
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = str(response.choices[0].message.content or "").strip()
        except RateLimitError:
            raise AnalyzeFailure("rate_limited") from None
        except (APIConnectionError, APITimeoutError):
            raise AnalyzeFailure("service_unavailable") from None
        except Exception:
            raise AnalyzeFailure("analysis_failed") from None
        try:
            parsed = _ProviderReport.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError):
            raise AnalyzeFailure("invalid_response") from None
        report = self._validated_report(
            parsed,
            report_id=report_id,
            question=question,
        )
        if not report.summary:
            raise AnalyzeFailure("invalid_response")
        return report

    @staticmethod
    def _clean(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    @classmethod
    def _items(cls, values: list[_ProviderItem], limit: int) -> tuple[CrownAnalyzeItem, ...]:
        result: list[CrownAnalyzeItem] = []
        for item in values[:limit]:
            title = cls._clean(item.title, 180)
            detail = cls._clean(item.detail, 1600)
            if not title and not detail:
                continue
            if not title:
                title = detail[:120]
            category = cls._clean(item.category, 48).lower()
            result.append(CrownAnalyzeItem(title, detail, category if category in _CATEGORIES else "unknown"))
        return tuple(result)

    @classmethod
    def _validated_report(
        cls,
        parsed: _ProviderReport,
        *,
        report_id: UUID,
        question: str,
    ) -> CrownAnalyzeReport:
        findings = cls._items(parsed.findings, 12)
        recommendations = cls._items(parsed.recommendations, 10)
        summary = cls._clean(parsed.summary, 2400)
        if not summary:
            first = findings[0] if findings else (recommendations[0] if recommendations else None)
            summary = first.detail or first.title if first is not None else ""
        warnings = tuple(filter(None, (cls._clean(item, 600) for item in parsed.warnings[:8])))
        evidence = tuple(
            CrownAnalyzeEvidence(
                observation=cls._clean(item.observation, 1200),
                visible_region=cls._clean(item.visible_region, 160),
            )
            for item in parsed.evidence[:12]
            if cls._clean(item.observation, 1200)
        )
        follow_up = tuple(filter(None, (cls._clean(item, 300) for item in parsed.follow_up_suggestions[:6])))
        return CrownAnalyzeReport(
            report_id=report_id,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            media_kind="image",
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            warnings=warnings,
            evidence=evidence,
            follow_up_suggestions=follow_up,
            question=cls._clean(question, 500),
        )
