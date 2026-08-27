from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.crown_core.action_planner import CrownActionPlanner
from app.crown_core.action_results import recent_action_results
from app.crown_core.contracts import (
    CrownAnalyzeReport,
    CrownPrincipal,
    CrownSkillBlock,
    CrownSkillResult,
    CrownTurnRequest,
    CrownTurnResult,
)
from app.crown_core.response import spoken_text
from app.services.brain.loadouts import ROLE_LOADOUTS


PartialCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class CrownCore:
    """One intelligence/personality/memory boundary for Telegram, Web and iOS."""

    conversation: Any
    store: Any
    profiles: Any
    analyzer: Any | None = None

    # Compatibility adapter used by established Telegram and Mini App routes.
    # Their server-resolved profile already contains the canonical identity.
    def reply(self, **kwargs: Any) -> str:
        return str(self.conversation.reply(**kwargs))

    def principal_for_authenticated_identity(self, provider: str, provider_subject: str) -> CrownPrincipal | None:
        resolver = getattr(self.store, "resolve_canonical_identity", None)
        if not callable(resolver):
            return None
        raw = resolver(str(provider), str(provider_subject))
        return self._principal(raw, provider=provider, provider_subject=provider_subject)

    def _principal(self, raw: Any, *, provider: str, provider_subject: str) -> CrownPrincipal | None:
        if not isinstance(raw, dict):
            return None
        try:
            from uuid import UUID

            canonical = UUID(str(raw.get("black_crown_user_id") or ""))
            owner = int(
                raw.get("legacy_owner_id")
                or (provider_subject if provider == "telegram" else "")
            )
        except (TypeError, ValueError):
            return None
        if str(raw.get("identity_status") or "") != "active":
            return None
        if str(raw.get("account_status") or "") != "active":
            return None
        return CrownPrincipal(canonical, str(provider), str(provider_subject), owner)

    def execute_turn(
        self,
        request: CrownTurnRequest,
        *,
        on_partial: PartialCallback | None = None,
    ) -> CrownTurnResult:
        profile = self.profiles.get(request.principal.legacy_owner_id)
        projected = str(profile.get("black_crown_user_id") or "")
        if projected != str(request.principal.black_crown_user_id):
            raise RuntimeError("canonical_identity_mismatch")
        history = list(self.store.get(request.principal.legacy_owner_id) or [])

        def guarded_partial(text: str, meta: dict[str, Any]) -> None:
            if on_partial is not None:
                on_partial(text, meta)

        reply_arguments: dict[str, Any] = {
            "text": request.text,
            "profile": profile,
            "history": history,
            "on_partial": guarded_partial if on_partial is not None else None,
        }
        server_context: dict[str, Any] = {}
        analysis_report_id = getattr(request, "analysis_report_id", None)
        if analysis_report_id is not None:
            report = self.analysis_report(request.principal, analysis_report_id)
            if report is None:
                raise RuntimeError("analysis_report_not_found")
            server_context["analysis_report"] = self._discussion_context(report)

        # Actual device execution results are canonical context, not model
        # claims. Only the bounded server-validated projection is exposed to the
        # next CROWN turn; raw EventKit identifiers and arbitrary client text are
        # never stored here.
        action_results = recent_action_results(self, request.principal, limit=5)
        if action_results:
            server_context["recent_action_results"] = action_results
        if server_context:
            reply_arguments["server_context"] = server_context

        # V1 semantic planning is deliberately bounded and deterministic. It
        # only recognizes high-confidence commands and emits an untrusted
        # proposal envelope; the closed action registry, device policy,
        # confirmation and executor remain authoritative.
        action_metadata = CrownActionPlanner().propose(
            text=request.text,
            source_turn_id=request.turn_id,
            analysis_report_id=analysis_report_id,
        )

        result = self.reply(
            **reply_arguments,
        )
        return CrownTurnResult(
            display_text=result,
            spoken_text=spoken_text(result),
            action_metadata=action_metadata,
        )

    async def execute_turn_async(
        self,
        request: CrownTurnRequest,
        *,
        on_partial: PartialCallback | None = None,
    ) -> CrownTurnResult:
        return await asyncio.to_thread(self.execute_turn, request, on_partial=on_partial)

    def brain_snapshot(self, principal: CrownPrincipal) -> dict[str, Any]:
        profile = self.profile_for(principal)
        if str(profile.get("black_crown_user_id") or "") != str(principal.black_crown_user_id):
            raise RuntimeError("canonical_identity_mismatch")
        clean_profile = {
            str(key): value
            for key, value in profile.items()
            if not str(key).startswith("_") and not str(key).startswith("crown_")
            and key != "black_crown_user_id"
        }
        return {
            "profile": clean_profile,
            "summary": str(self.store.get_summary(principal.legacy_owner_id) or "")[:4000],
            "derived": dict(self.store.get_derived_intelligence(principal.legacy_owner_id) or {}),
        }

    def profile_for(self, principal: CrownPrincipal) -> dict[str, Any]:
        profile = dict(self.profiles.get(principal.legacy_owner_id) or {})
        if str(profile.get("black_crown_user_id") or "") != str(principal.black_crown_user_id):
            raise RuntimeError("canonical_identity_mismatch")
        return profile

    def patch_brain(self, principal: CrownPrincipal, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
        clean = {str(k): v for k, v in patch.items() if k in allowed and isinstance(v, str)}
        clean = {key: value.strip()[:240] for key, value in clean.items() if value.strip()}
        if not clean:
            raise ValueError("empty_patch")
        self.profiles.patch(principal.legacy_owner_id, clean)
        return self.brain_snapshot(principal)

    def analyze_image(
        self,
        principal: CrownPrincipal,
        *,
        payload: bytes,
        declared_mime: str,
        question: str,
        locale: str,
        report_id: Any,
    ) -> CrownAnalyzeReport:
        if self.analyzer is None:
            from app.services.analyze import AnalyzeFailure

            raise AnalyzeFailure("service_unavailable")
        existing = self.analysis_report(principal, report_id)
        if existing is not None:
            return self._report_from_projection(existing)
        report = self.analyzer.analyze(
            payload=payload,
            declared_mime=declared_mime,
            profile=self.profile_for(principal),
            question=question,
            locale=locale,
            report_id=report_id,
        )
        self.store.add_episode(
            principal.legacy_owner_id,
            {"kind": "analyze_report", "report": report.projection()},
        )
        return report

    def list_analysis_reports(
        self,
        principal: CrownPrincipal,
        *,
        cursor: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        try:
            offset = max(0, int(cursor or "0"))
        except ValueError:
            raise ValueError("invalid_cursor") from None
        page_limit = max(1, min(int(limit), 20))
        episodes = list(self.store.list_episodes(principal.legacy_owner_id, 100) or [])
        reports = [
            dict(item.get("report") or {})
            for item in episodes
            if isinstance(item, dict)
            and item.get("kind") == "analyze_report"
            and isinstance(item.get("report"), dict)
        ]
        page = reports[offset: offset + page_limit]
        next_cursor = str(offset + len(page)) if offset + len(page) < len(reports) else None
        return {"reports": page, "next_cursor": next_cursor}

    def analysis_report(self, principal: CrownPrincipal, report_id: Any) -> dict[str, Any] | None:
        expected = str(report_id)
        episodes = list(self.store.list_episodes(principal.legacy_owner_id, 100) or [])
        for item in episodes:
            if not isinstance(item, dict) or item.get("kind") != "analyze_report":
                continue
            report = item.get("report")
            if isinstance(report, dict) and str(report.get("id") or "") == expected:
                return dict(report)
        return None

    @staticmethod
    def _discussion_context(report: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(report.get("id") or ""),
            "summary": str(report.get("summary") or "")[:2400],
            "findings": list(report.get("findings") or [])[:12],
            "recommendations": list(report.get("recommendations") or [])[:10],
            "warnings": list(report.get("warnings") or [])[:8],
            "evidence": list(report.get("evidence") or [])[:12],
        }

    @staticmethod
    def _report_from_projection(value: dict[str, Any]) -> CrownAnalyzeReport:
        from uuid import UUID
        from app.crown_core.contracts import CrownAnalyzeEvidence, CrownAnalyzeItem

        def items(key: str) -> tuple[CrownAnalyzeItem, ...]:
            return tuple(
                CrownAnalyzeItem(
                    str(item.get("title") or "")[:180],
                    str(item.get("detail") or "")[:1600],
                    str(item.get("category") or "unknown")[:48],
                )
                for item in list(value.get(key) or [])[:12]
                if isinstance(item, dict)
            )

        evidence = tuple(
            CrownAnalyzeEvidence(
                str(item.get("observation") or "")[:1200],
                str(item.get("visible_region") or "")[:160],
            )
            for item in list(value.get("evidence") or [])[:12]
            if isinstance(item, dict)
        )
        return CrownAnalyzeReport(
            report_id=UUID(str(value.get("id") or "")),
            created_at=str(value.get("created_at") or ""),
            media_kind=str(value.get("media_kind") or "image"),
            summary=str(value.get("summary") or "")[:2400],
            findings=items("findings"),
            recommendations=items("recommendations"),
            warnings=tuple(str(item)[:600] for item in list(value.get("warnings") or [])[:8]),
            evidence=evidence,
            follow_up_suggestions=tuple(
                str(item)[:300] for item in list(value.get("follow_up_suggestions") or [])[:6]
            ),
            question=str(value.get("question") or "")[:500],
        )

    def read_skill(
        self,
        principal: CrownPrincipal,
        identifier: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return a bounded, read-only projection for an allow-listed native skill."""
        profile = self.profile_for(principal)

        if identifier == "player_brain_read":
            return self.brain_snapshot(principal)
        if identifier == "game_intel_read":
            return {
                "game": str(profile.get("game") or "")[:80],
                "mode": str(profile.get("mode") or "")[:80],
                "derived": dict(self.store.get_derived_intelligence(principal.legacy_owner_id) or {}),
            }
        if identifier == "loadout_read":
            game = str(profile.get("game") or "warzone").strip().lower()
            role = str(profile.get("role") or profile.get("playstyle") or "").strip().lower()
            game_loadouts = ROLE_LOADOUTS.get(game, {})
            selected = game_loadouts.get(role)
            return {
                "game": game,
                "role": role or None,
                "selected": dict(selected) if isinstance(selected, dict) else None,
                "available": {key: dict(value) for key, value in game_loadouts.items()},
            }
        if identifier == "training_summary_read":
            reader = getattr(self.store, "list_training_sessions", None)
            sessions = list(reader(principal.legacy_owner_id) or [])[:10] if callable(reader) else []
            return {"sessions": [self._safe_record(item) for item in sessions]}
        if identifier == "history_summary_read":
            all_history = list(self.store.get(principal.legacy_owner_id) or [])
            try:
                offset = max(0, int(cursor or "0"))
            except ValueError:
                raise ValueError("invalid_cursor") from None
            page_limit = max(1, min(int(limit), 50))
            end = max(0, len(all_history) - offset)
            start = max(0, end - page_limit)
            history = all_history[start:end]
            messages = []
            for item in history:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "").lower()
                content = str(item.get("content") or item.get("text") or "").strip()
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content[:2000]})
            result = {"messages": messages, "count": len(messages)}
            if start > 0:
                result["next_cursor"] = str(offset + len(history))
            return result
        raise ValueError("skill_not_available")

    def skill_result(
        self,
        principal: CrownPrincipal,
        identifier: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> CrownSkillResult:
        data = self.read_skill(principal, identifier, cursor=cursor, limit=limit)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        title, summary, blocks, warnings = self._skill_projection(identifier, data)
        return CrownSkillResult(
            skill_id=identifier,
            title=title,
            summary=summary,
            blocks=tuple(blocks),
            data=data,
            freshness_timestamp=now,
            warnings=tuple(warnings),
            next_cursor=str(data.get("next_cursor")) if data.get("next_cursor") else None,
        )

    @staticmethod
    def _skill_projection(
        identifier: str,
        data: dict[str, Any],
    ) -> tuple[str, str, list[CrownSkillBlock], list[str]]:
        if identifier == "player_brain_read":
            summary = str(data.get("summary") or "No Player Brain summary is available.")
            return (
                "Player Brain",
                summary[:500],
                [
                    CrownSkillBlock("text", {"text": summary[:4000]}),
                    CrownSkillBlock("metric", {"values": dict(data.get("derived") or {})}),
                ],
                [],
            )
        if identifier == "game_intel_read":
            game = str(data.get("game") or "Unknown game")
            mode = str(data.get("mode") or "Unknown mode")
            return (
                "Game Intelligence",
                f"{game} / {mode}",
                [
                    CrownSkillBlock("metric", {"values": dict(data.get("derived") or {})}),
                    CrownSkillBlock("evidence", {"source": "canonical_player_brain", "freshness": "server"}),
                ],
                ["freshness_depends_on_latest_server_observation"],
            )
        if identifier == "loadout_read":
            selected = data.get("selected") if isinstance(data.get("selected"), dict) else None
            return (
                "Loadout",
                "Saved role loadout" if selected else "No role-specific loadout is selected.",
                [
                    CrownSkillBlock(
                        "loadout",
                        {
                            "game": data.get("game"),
                            "role": data.get("role"),
                            "selected": selected,
                            "available": dict(data.get("available") or {}),
                        },
                    )
                ],
                [] if selected else ["no_selected_loadout"],
            )
        if identifier == "training_summary_read":
            sessions = list(data.get("sessions") or [])
            return (
                "Training Summary",
                f"{len(sessions)} recent training sessions.",
                [CrownSkillBlock("timeline", {"items": sessions})],
                [],
            )
        if identifier == "history_summary_read":
            messages = list(data.get("messages") or [])
            return (
                "History Summary",
                f"{len(messages)} recent conversation messages.",
                [CrownSkillBlock("timeline", {"items": messages})],
                [],
            )
        raise ValueError("skill_not_available")

    @staticmethod
    def _safe_record(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {
                str(key): item
                for key, item in value.items()
                if not str(key).startswith("_")
            }
        return {"value": str(value)[:2000]}
