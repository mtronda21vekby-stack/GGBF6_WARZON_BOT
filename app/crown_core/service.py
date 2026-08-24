from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.crown_core.contracts import CrownPrincipal, CrownTurnRequest, CrownTurnResult
from app.crown_core.response import spoken_text


PartialCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class CrownCore:
    """One intelligence/personality/memory boundary for Telegram, Web and iOS."""

    conversation: Any
    store: Any
    profiles: Any

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

        result = self.reply(
            text=request.text,
            profile=profile,
            history=history,
            on_partial=guarded_partial if on_partial is not None else None,
        )
        return CrownTurnResult(display_text=result, spoken_text=spoken_text(result))

    async def execute_turn_async(
        self,
        request: CrownTurnRequest,
        *,
        on_partial: PartialCallback | None = None,
    ) -> CrownTurnResult:
        return await asyncio.to_thread(self.execute_turn, request, on_partial=on_partial)

    def brain_snapshot(self, principal: CrownPrincipal) -> dict[str, Any]:
        profile = self.profiles.get(principal.legacy_owner_id)
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

    def patch_brain(self, principal: CrownPrincipal, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"current_goal", "training_focus", "weekly_focus", "playstyle"}
        clean = {str(k): v for k, v in patch.items() if k in allowed and isinstance(v, str)}
        clean = {key: value.strip()[:240] for key, value in clean.items() if value.strip()}
        if not clean:
            raise ValueError("empty_patch")
        self.profiles.patch(principal.legacy_owner_id, clean)
        return self.brain_snapshot(principal)
