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

        # Actual device action outcomes are canonical context, not model claims.
        # The bounded server-validated projection can include success, denial,
        # rejection, failure or cancellation, but never raw EventKit identifiers,
        # arbitrary client prose or associated local error values.
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

    def _report_from_projection(self, value: dict[str, Any]) -> CrownAnalyzeReport:
        return CrownAnalyzeReport.from_projection(value)

    def skill(self, principal: CrownPrincipal, skill_id: str, *, cursor: str | None = None) -> CrownSkillResult:
        if skill_id == "player_brain_read":
            brain = self.brain_snapshot(principal)
            return CrownSkillResult(
                capability="player_brain_read",
                skill_id=skill_id,
                title="Player Brain",
                summary=str(brain.get("summary") or ""),
                blocks=[CrownSkillBlock("profile", brain.get("profile") or {})],
                data=brain,
                freshness_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        if skill_id == "history_summary_read":
            history = list(self.store.get(principal.legacy_owner_id) or [])
            page_size = 20
            try:
                offset = max(0, int(cursor or "0"))
            except ValueError:
                raise ValueError("invalid_cursor") from None
            page = history[offset: offset + page_size]
            next_cursor = str(offset + len(page)) if offset + len(page) < len(history) else None
            return CrownSkillResult(
                capability="history_summary_read",
                skill_id=skill_id,
                title="History",
                summary="Recent canonical conversation history.",
                blocks=[CrownSkillBlock("messages", {"count": len(page)})],
                data={"messages": page},
                freshness_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                next_cursor=next_cursor,
            )
        if skill_id == "loadout_read":
            profile = self.profile_for(principal)
            game = str(profile.get("game") or profile.get("active_game") or "warzone").lower()
            data = ROLE_LOADOUTS.get(game) or ROLE_LOADOUTS.get("warzone") or {}
            return CrownSkillResult(
                capability="loadout_read",
                skill_id=skill_id,
                title="Loadouts",
                summary=f"Canonical {game} loadout reference.",
                blocks=[CrownSkillBlock("loadouts", data if isinstance(data, dict) else {})],
                data={"game": game, "loadouts": data},
                freshness_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        if skill_id == "training_summary_read":
            profile = self.profile_for(principal)
            data = {
                "current_goal": profile.get("current_goal"),
                "training_focus": profile.get("training_focus"),
                "weekly_focus": profile.get("weekly_focus"),
                "playstyle": profile.get("playstyle"),
            }
            return CrownSkillResult(
                capability="training_summary_read",
                skill_id=skill_id,
                title="Training",
                summary="Canonical training focus from Player Brain.",
                blocks=[CrownSkillBlock("training", data)],
                data=data,
                freshness_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        if skill_id == "game_intel_read":
            profile = self.profile_for(principal)
            game = str(profile.get("game") or profile.get("active_game") or "warzone").lower()
            data = {
                "game": game,
                "current_goal": profile.get("current_goal"),
                "playstyle": profile.get("playstyle"),
            }
            return CrownSkillResult(
                capability="game_intel_read",
                skill_id=skill_id,
                title="Game Intel",
                summary=f"Current canonical context for {game}.",
                blocks=[CrownSkillBlock("game_intel", data)],
                data=data,
                freshness_timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        raise ValueError("unknown_skill")
